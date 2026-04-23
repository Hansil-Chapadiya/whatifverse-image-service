from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.security import validate_internal_token
from app.db.session import is_db_enabled
from app.schemas.requests.asset_request import AssetCreateRequest
from app.schemas.responses.asset_response import JobAcceptedResponse, SceneAssetResponse
from app.services.asset_pipeline_service import PipelineResult, asset_pipeline_service
from app.services.idempotency_service import idempotency_service
from app.services.scene_store import scene_store

router = APIRouter(prefix="/scenes", tags=["scenes"], dependencies=[Depends(validate_internal_token)])


def _payload_for_hash(request: AssetCreateRequest) -> dict:
    payload = request.model_dump(mode="json", exclude_none=True)
    payload.pop("request_id", None)
    return payload


def _build_scene_response(result: dict, replay: bool = False) -> SceneAssetResponse:
    payload = {**result, "idempotent_replay": replay}
    return SceneAssetResponse(**payload)


def _build_generation_error(exc: Exception) -> dict:
    return {
        "code": "ASSET_GENERATION_FAILED",
        "message": "Failed to generate GLB assets",
        "details": str(exc),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _resolve_scene_title(request: AssetCreateRequest) -> str:
    if request.scene_title:
        return request.scene_title.strip()

    compact_text = " ".join(request.scenario_text.split())
    if len(compact_text) <= 80:
        return compact_text
    return f"{compact_text[:77].rstrip()}..."


def _build_scene_stub(scene_id: str, request: AssetCreateRequest, status_value: str) -> dict:
    return {
        "scene_id": scene_id,
        "status": status_value,
        "scene_title": _resolve_scene_title(request),
        "scenario_text": request.scenario_text,
        "assets": None,
    }


def _persist_pipeline_result(
    result: PipelineResult,
    request: AssetCreateRequest,
    payload_hash: str,
) -> dict:
    scene_store.save_scene(
        result.scene_id,
        result.response_payload,
        request_id=request.request_id,
        payload_hash=payload_hash,
        entity_records=result.entity_records,
        asset_records=result.asset_records,
    )
    if request.request_id:
        idempotency_service.set_response(request.request_id, payload_hash, result.response_payload)
    return result.response_payload


def _run_job(job_id: str, scene_id: str, request: AssetCreateRequest, payload_hash: str) -> None:
    scene_store.set_job_status(job_id, "processing")
    scene_store.save_scene(
        scene_id,
        _build_scene_stub(scene_id, request, "processing"),
        request_id=request.request_id,
        payload_hash=payload_hash,
    )
    try:
        result = asset_pipeline_service.run(scene_id, request)
        response_payload = _persist_pipeline_result(result, request, payload_hash)
        scene_store.set_job_result(job_id, response_payload)
    except Exception as exc:
        scene_store.set_job_error(job_id, scene_id, _build_generation_error(exc))
        scene_store.save_scene(
            scene_id,
            _build_scene_stub(scene_id, request, "failed"),
            request_id=request.request_id,
            payload_hash=payload_hash,
        )
        if request.request_id:
            idempotency_service.clear_record(request.request_id)


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

    if mode == "async" and not is_db_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "ASYNC_MODE_REQUIRES_DATABASE",
                    "message": "async mode requires DATABASE_URL-backed persistence",
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
            return _build_scene_response(current.response, replay=True)

    scene_id = f"scn_{uuid4().hex[:12]}"
    if mode == "async":
        job_id = f"job_{uuid4().hex[:12]}"
        scene_store.save_scene(
            scene_id,
            _build_scene_stub(scene_id, request, "queued"),
            request_id=request.request_id,
            payload_hash=payload_hash,
        )
        scene_store.create_job(job_id, scene_id)
        background_tasks.add_task(_run_job, job_id, scene_id, request, payload_hash)
        return JobAcceptedResponse(job_id=job_id, status="queued", scene_id=scene_id)

    try:
        result = asset_pipeline_service.run(scene_id, request)
        response_payload = _persist_pipeline_result(result, request, payload_hash)
    except Exception:
        if request.request_id:
            idempotency_service.clear_record(request.request_id)
        raise

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
