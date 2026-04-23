from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AssetInfo(BaseModel):
    image_url: str
    public_id: str
    format: str
    width: int
    height: int


class EntityAsset(BaseModel):
    name: str
    image_url: str
    public_id: str
    position: list[float]
    scale: float


class SceneAssets(BaseModel):
    scene_image: AssetInfo
    entities: list[EntityAsset]


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


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    scene_id: str
    result: SceneAssetResponse | None = None


class ErrorEnvelope(BaseModel):
    timestamp: datetime
    error: dict
