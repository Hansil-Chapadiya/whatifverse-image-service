from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.db.models.asset_model import JobModel, SceneModel
from app.db.session import SessionLocal


@dataclass
class JobRecord:
    scene_id: str
    status: str
    result: dict[str, Any] | None = None


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
    ) -> None:
        with self._lock:
            self._scene_results[scene_id] = payload

        if SessionLocal is None:
            return

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
            else:
                if request_id:
                    scene.request_id = request_id
                if payload_hash:
                    scene.payload_hash = payload_hash
                scene.scene_title = str(payload.get("scene_title", scene.scene_title))
                scene.scenario_text = str(payload.get("scenario_text", scene.scenario_text))
                scene.status = str(payload.get("status", scene.status))
                scene.response_json = payload
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

    def get_job(self, job_id: str) -> JobRecord | None:
        if SessionLocal is None:
            return None

        with SessionLocal() as db:
            job = db.get(JobModel, job_id)
            if job is None:
                return None
            return JobRecord(scene_id=job.scene_id, status=job.status, result=job.result_json)


scene_store = SceneStore()
