from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntityInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    position: list[float] | None = Field(default=None, min_length=3, max_length=3)
    scale: float | None = Field(default=None, gt=0)


class RenderOptions(BaseModel):
    style: str | None = None
    format: Literal["png", "jpg", "webp"] | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    negative_prompt: str | None = None
    include_preview_assets: bool = False


class AssetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(default=None, min_length=8, max_length=128)
    scene_title: str | None = Field(default=None, max_length=200)
    scenario_text: str = Field(min_length=1)
    entities: list[EntityInput] = Field(min_length=1)
    render_options: RenderOptions | None = None

    @field_validator("entities", mode="before")
    @classmethod
    def normalize_entities(cls, value: object) -> object:
        if not isinstance(value, list):
            return value

        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"name": item})
            else:
                normalized.append(item)
        return normalized

    @field_validator("entities")
    @classmethod
    def ensure_unique_entities(cls, entities: list[EntityInput]) -> list[EntityInput]:
        names = [item.name.strip().lower() for item in entities]
        if len(names) != len(set(names)):
            raise ValueError("Entity names must be unique")
        return entities


class CreateModeQuery(BaseModel):
    mode: Literal["sync", "async"] = "sync"
