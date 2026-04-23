from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SceneModel(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"scn_{uuid4().hex[:12]}")
    request_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    scene_title: Mapped[str] = mapped_column(String(200))
    scenario_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    response_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entities: Mapped[list["SceneEntityModel"]] = relationship(back_populates="scene", cascade="all, delete-orphan")
    assets: Mapped[list["AssetModel"]] = relationship(back_populates="scene", cascade="all, delete-orphan")


class SceneEntityModel(Base):
    __tablename__ = "scene_entities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"ent_{uuid4().hex[:12]}")
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    position_x: Mapped[float] = mapped_column(Float, default=0)
    position_y: Mapped[float] = mapped_column(Float, default=0)
    position_z: Mapped[float] = mapped_column(Float, default=0)
    scale: Mapped[float] = mapped_column(Float, default=1)

    scene: Mapped[SceneModel] = relationship(back_populates="entities")


class AssetModel(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"ast_{uuid4().hex[:12]}")
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(ForeignKey("scene_entities.id", ondelete="SET NULL"), nullable=True)
    asset_kind: Mapped[str] = mapped_column(String(32))
    storage_provider: Mapped[str] = mapped_column(String(20), default="cloudinary")
    public_id: Mapped[str] = mapped_column(String(255))
    secure_url: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(16))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    generation_params_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)

    scene: Mapped[SceneModel] = relationship(back_populates="assets")


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IdempotencyModel(Base):
    __tablename__ = "idempotency_records"

    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    response_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
