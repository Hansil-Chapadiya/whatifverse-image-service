from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.security import validate_internal_token
from app.schemas.requests.asset_request import AssetCreateRequest
from app.schemas.responses.asset_response import JobAcceptedResponse, SceneAssetResponse
from app.services.asset_pipeline_service import asset_pipeline_service
from app.services.idempotency_service import idempotency_service
from app.services.scene_store import scene_store

router = APIRouter(prefix="/scenes", tags=["scenes"], dependencies=[Depends(validate_internal_token)])


def _payload_for_hash(request: AssetCreateRequest) -> dict:
    payload = request.model_dump(mode="json", exclude_none=True)
    payload.pop("request_id", None)
    return payload


def _build_scene_response(result: dict, replay: bool = False) -> SceneAssetResponse:
    return SceneAssetResponse(
        scene_id=result["scene_id"],
        status=result["status"],
        scene_title=result["scene_title"],
        scenario_text=result["scenario_text"],
        assets=result.get("assets"),
        idempotent_replay=replay,
    )


def _run_job(job_id: str, request: AssetCreateRequest, request_id: str | None = None, payload_hash: str | None = None) -> None:
    scene_store.set_job_status(job_id, "processing")
    result = asset_pipeline_service.run(request)
    response_payload = {
        "scene_id": result.scene_id,
        "status": "completed",
        "scene_title": result.scene_title,
        "scenario_text": result.scenario_text,
        "assets": {
            "scene_image": result.scene_asset,
            "entities": result.entity_assets,
        },
    }
    scene_store.save_scene(result.scene_id, response_payload, request_id=request_id, payload_hash=payload_hash)
    scene_store.set_job_result(job_id, response_payload)
    if request_id and payload_hash:
        idempotency_service.set_response(request_id, payload_hash, response_payload)


@router.post("/assets", response_model=SceneAssetResponse | JobAcceptedResponse)
def create_scene_assets(
    request: AssetCreateRequest,
    background_tasks: BackgroundTasks,
    mode: str = Query(default="sync", pattern="^(sync|async)$"),
):
    if len(request.entities) > settings.max_entities_per_scene:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MAX_ENTITIES_EXCEEDED",
                    "message": f"entities cannot exceed {settings.max_entities_per_scene}",
                }
            },
        )

    payload_hash = idempotency_service.compute_payload_hash(_payload_for_hash(request))
    if request.request_id:
        current = idempotency_service.assert_or_create(request.request_id, payload_hash)
        if current:
            if current.payload_hash != payload_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH",
                            "message": "request_id already exists with a different payload",
                        }
                    },
                )
            if current.response is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "IDEMPOTENCY_REQUEST_IN_PROGRESS",
                            "message": "request_id is already being processed",
                        }
                    },
                )
            if current.response is not None:
                return _build_scene_response(current.response, replay=True)

    if mode == "async":
        temp_scene_id = f"scn_{uuid4().hex[:12]}"
        job_id = f"job_{uuid4().hex[:12]}"
        scene_store.create_job(job_id, temp_scene_id)
        background_tasks.add_task(_run_job, job_id, request, request.request_id, payload_hash)
        return JobAcceptedResponse(job_id=job_id, status="queued", scene_id=temp_scene_id)

    result = asset_pipeline_service.run(request)
    response_payload = {
        "scene_id": result.scene_id,
        "status": "completed",
        "scene_title": result.scene_title,
        "scenario_text": result.scenario_text,
        "assets": {
            "scene_image": result.scene_asset,
            "entities": result.entity_assets,
        },
    }
    scene_store.save_scene(
        result.scene_id,
        response_payload,
        request_id=request.request_id,
        payload_hash=payload_hash,
    )

    if request.request_id:
        idempotency_service.set_response(request.request_id, payload_hash, response_payload)

    return _build_scene_response(response_payload)


@router.get("/{scene_id}", response_model=SceneAssetResponse)
def get_scene(scene_id: str):
    data = scene_store.get_scene(scene_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SCENE_NOT_FOUND",
                    "message": "scene_id was not found",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    return _build_scene_response(data)


