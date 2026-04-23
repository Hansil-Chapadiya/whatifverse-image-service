from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AssetFileInfo(BaseModel):
    url: str
    public_id: str
    format: str
    resource_type: Literal["image", "raw"]
    bytes_size: int | None = None
    width: int | None = None
    height: int | None = None


class SceneAssetBundle(BaseModel):
    preview_image: AssetFileInfo | None = None
    glb_model: AssetFileInfo


class EntityAssetBundle(BaseModel):
    name: str
    position: list[float]
    scale: float
    preview_image: AssetFileInfo | None = None
    glb_model: AssetFileInfo


class SceneAssets(BaseModel):
    scene: SceneAssetBundle
    entities: list[EntityAssetBundle]


class SceneAssetResponse(BaseModel):
    scene_id: str
    status: Literal["completed", "processing", "queued", "failed"]
    scene_title: str
    scenario_text: str
    assets: SceneAssets | None = None
    idempotent_replay: bool = False


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing"]
    scene_id: str


class JobErrorResponse(BaseModel):
    code: str
    message: str
    details: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    scene_id: str
    result: SceneAssetResponse | None = None
    error: JobErrorResponse | None = None


class ErrorEnvelope(BaseModel):
    timestamp: datetime
    error: dict
