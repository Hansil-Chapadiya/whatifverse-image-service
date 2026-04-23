from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.db.models.asset_model import AssetModel, JobModel, SceneEntityModel, SceneModel
from app.db.session import SessionLocal


@dataclass
class JobRecord:
    scene_id: str
    status: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class SceneStore:
    def __init__(self) -> None:
        self._scene_results: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def save_scene(
        self,
        scene_id: str,
        payload: dict[str, Any],
        request_id: str | None = None,
        payload_hash: str | None = None,
        entity_records: list[dict[str, Any]] | None = None,
        asset_records: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._lock:
            self._scene_results[scene_id] = payload

        if SessionLocal is None:
            return

        entity_records = entity_records or []
        asset_records = asset_records or []

        with SessionLocal() as db:
            scene = db.get(SceneModel, scene_id)
            if scene is None:
                scene = SceneModel(
                    id=scene_id,
                    request_id=request_id,
                    payload_hash=payload_hash,
                    scene_title=str(payload.get("scene_title", "")),
                    scenario_text=str(payload.get("scenario_text", "")),
                    status=str(payload.get("status", "completed")),
                    response_json=payload,
                )
                db.add(scene)
                db.flush()
            else:
                if request_id:
                    scene.request_id = request_id
                if payload_hash:
                    scene.payload_hash = payload_hash
                scene.scene_title = str(payload.get("scene_title", scene.scene_title))
                scene.scenario_text = str(payload.get("scenario_text", scene.scenario_text))
                scene.status = str(payload.get("status", scene.status))
                scene.response_json = payload

            db.query(AssetModel).filter(AssetModel.scene_id == scene_id).delete(synchronize_session=False)
            db.query(SceneEntityModel).filter(SceneEntityModel.scene_id == scene_id).delete(synchronize_session=False)

            entity_ids_by_name: dict[str, str] = {}
            for entity_record in entity_records:
                position = entity_record.get("position") or [0.0, 0.0, 0.0]
                entity = SceneEntityModel(
                    scene_id=scene_id,
                    name=str(entity_record["name"]),
                    position_x=float(position[0]),
                    position_y=float(position[1]),
                    position_z=float(position[2]),
                    scale=float(entity_record.get("scale", 1.0)),
                )
                db.add(entity)
                db.flush()
                entity_ids_by_name[entity.name] = entity.id

            for asset_record in asset_records:
                db.add(
                    AssetModel(
                        scene_id=scene_id,
                        entity_id=entity_ids_by_name.get(asset_record.get("entity_name")),
                        asset_kind=str(asset_record["asset_kind"]),
                        storage_provider="cloudinary",
                        public_id=str(asset_record["public_id"]),
                        secure_url=str(asset_record["secure_url"]),
                        format=str(asset_record["format"]),
                        width=int(asset_record.get("width", 0) or 0),
                        height=int(asset_record.get("height", 0) or 0),
                        generation_params_json=dict(asset_record.get("generation_params_json") or {}),
                        revision=int(asset_record.get("revision", 1)),
                    )
                )

            db.commit()

    def get_scene(self, scene_id: str) -> dict[str, Any] | None:
        cached = self._scene_results.get(scene_id)
        if cached is not None:
            return cached

        if SessionLocal is None:
            return None

        with SessionLocal() as db:
            scene = db.get(SceneModel, scene_id)
            if scene and scene.response_json:
                return scene.response_json
        return None

    def create_job(self, job_id: str, scene_id: str) -> None:
        if SessionLocal is None:
            return

        with SessionLocal() as db:
            db.add(JobModel(id=job_id, scene_id=scene_id, status="queued", result_json=None))
            db.commit()

    def set_job_status(self, job_id: str, status: str) -> None:
        if SessionLocal is None:
            return

        with SessionLocal() as db:
            job = db.get(JobModel, job_id)
            if job:
                job.status = status
                db.commit()

    def set_job_result(self, job_id: str, result: dict[str, Any], status: str = "completed") -> None:
        if SessionLocal is None:
            return

        with SessionLocal() as db:
            job = db.get(JobModel, job_id)
            if job:
                job.status = status
                job.scene_id = str(result.get("scene_id", job.scene_id))
                job.result_json = result
                db.commit()

    def set_job_error(self, job_id: str, scene_id: str, error: dict[str, Any]) -> None:
        if SessionLocal is None:
            return

        with SessionLocal() as db:
            job = db.get(JobModel, job_id)
            if job:
                job.status = "failed"
                job.scene_id = scene_id
                job.result_json = {"error": error}
                db.commit()

    def get_job(self, job_id: str) -> JobRecord | None:
        if SessionLocal is None:
            return None

        with SessionLocal() as db:
            job = db.get(JobModel, job_id)
            if job is None:
                return None

            error = None
            result = job.result_json
            if job.status == "failed" and isinstance(job.result_json, dict):
                possible_error = job.result_json.get("error")
                if isinstance(possible_error, dict):
                    error = possible_error
                    result = None

            return JobRecord(scene_id=job.scene_id, status=job.status, result=result, error=error)


scene_store = SceneStore()
