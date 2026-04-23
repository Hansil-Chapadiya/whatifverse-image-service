from dataclasses import dataclass
import re

from app.clients.cloudinary_client import CloudinaryUploadResult, CloudinaryClient
from app.clients.hf_image_client import HFImageClient
from app.core.config import settings
from app.schemas.requests.asset_request import AssetCreateRequest
from app.services.glb_builder_service import ScenePlane, glb_builder_service


@dataclass
class PipelineResult:
    scene_id: str
    response_payload: dict
    entity_records: list[dict]
    asset_records: list[dict]


class AssetPipelineService:
    def __init__(self) -> None:
        self.hf_image_client = HFImageClient()
        self.cloudinary_client = CloudinaryClient()

    @staticmethod
    def _resolve_scene_title(request: AssetCreateRequest) -> str:
        if request.scene_title:
            return request.scene_title.strip()

        compact_text = " ".join(request.scenario_text.split())
        if len(compact_text) <= 80:
            return compact_text
        return f"{compact_text[:77].rstrip()}..."

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
        collapsed = "-".join(part for part in cleaned.split("-") if part)
        return collapsed or "asset"

    @staticmethod
    def _build_negative_prompt(*parts: str | None) -> str | None:
        cleaned_parts: list[str] = []
        seen: set[str] = set()
        for part in parts:
            if not part:
                continue
            for token in (item.strip() for item in part.split(",")):
                if not token:
                    continue
                lowered = token.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                cleaned_parts.append(token)
        if not cleaned_parts:
            return None
        return ", ".join(cleaned_parts)

    @staticmethod
    def _build_background_prompt(scenario_text: str, style: str, entity_names: list[str]) -> str:
        entity_clause = ""
        if entity_names:
            entity_clause = (
                " Keep these subjects out of the frame because they will be generated as separate AR objects: "
                f"{', '.join(entity_names)}."
            )

        return (
            f"Scenario: {scenario_text}. "
            f"Create only the background/world setting in style: {style}. "
            "No single hero subject, no isolated character, no centered deity, no portrait, no cutout object, no text. "
            "Think of this as an environmental background plate for AR placement."
            f"{entity_clause}"
        )

    @staticmethod
    def _build_entity_context(entity_name: str, scenario_text: str, other_entity_names: list[str]) -> str:
        compact_scenario = " ".join(scenario_text.split())
        if not compact_scenario:
            return ""

        lowered_scenario = compact_scenario.lower()
        search_terms = sorted(
            {
                token.lower()
                for token in re.findall(r"[A-Za-z0-9]+", entity_name)
                if len(token) > 2
            },
            key=len,
            reverse=True,
        )

        subject_context = compact_scenario
        for term in search_terms:
            index = lowered_scenario.find(term)
            if index == -1:
                continue
            start = max(0, index - 60)
            end = min(len(compact_scenario), index + len(term) + 60)
            subject_context = compact_scenario[start:end].strip(" ,.;:-")
            break

        for other_entity_name in other_entity_names:
            for token in sorted(
                {
                    token
                    for token in re.findall(r"[A-Za-z0-9]+", other_entity_name)
                    if len(token) > 2
                },
                key=len,
                reverse=True,
            ):
                subject_context = re.sub(rf"\b{re.escape(token)}\b", "", subject_context, flags=re.IGNORECASE)

        return " ".join(subject_context.split())

    @staticmethod
    def _is_world_entity(entity_name: str) -> bool:
        lowered_name = entity_name.lower()
        world_keywords = (
            "galaxy",
            "milky way",
            "universe",
            "planet",
            "earth",
            "mars",
            "moon",
            "sun",
            "star",
            "nebula",
            "ocean",
            "sea",
            "mountain",
            "forest",
            "sky",
            "space",
            "city",
            "temple",
            "world",
        )
        return any(keyword in lowered_name for keyword in world_keywords)

    @staticmethod
    def _build_entity_prompt(
        entity_name: str,
        scenario_text: str,
        style: str,
        other_entity_names: list[str],
    ) -> str:
        context_clause = ""
        world_entity = AssetPipelineService._is_world_entity(entity_name)
        subject_context = ""
        if not world_entity:
            subject_context = AssetPipelineService._build_entity_context(entity_name, scenario_text, other_entity_names)
        if subject_context:
            context_clause = (
                " Use this subject-specific scenario context only for subtle styling, not as a source of extra subjects: "
                f"{subject_context}."
            )

        exclusion_clause = ""
        if other_entity_names:
            exclusion_clause = f" Do not include these other entities: {', '.join(other_entity_names)}."

        final_guidance = (
            "Represent it as one standalone iconic visual object suitable for AR placement."
            if world_entity
            else "Preserve clear subject identity and keep the silhouette readable for AR placement."
        )

        return (
            f"Create exactly one isolated AR-ready subject: {entity_name}. "
            f"Render style: {style}. "
            "Single subject only, centered, full object or full figure, clean empty background, no environment, no scenery, no extra characters, no text, no watermark. "
            "This asset will be placed separately in AR, so do not generate a full scene."
            f"{context_clause}"
            f"{exclusion_clause} "
            f"{final_guidance}"
        )

    @staticmethod
    def _build_asset_file(upload: CloudinaryUploadResult) -> dict:
        width = upload.width if upload.width > 0 else None
        height = upload.height if upload.height > 0 else None
        return {
            "url": upload.secure_url,
            "public_id": upload.public_id,
            "format": upload.format,
            "resource_type": upload.resource_type,
            "bytes_size": upload.bytes_size,
            "width": width,
            "height": height,
        }

    @staticmethod
    def _should_upload_previews(request: AssetCreateRequest) -> bool:
        caller_requested = bool(request.render_options and request.render_options.include_preview_assets)
        if settings.persist_preview_assets:
            return True
        if not caller_requested:
            return False
        return settings.debug or settings.allow_preview_asset_uploads

    @staticmethod
    def _build_db_asset_record(
        *,
        scene_id: str,
        entity_name: str | None,
        asset_kind: str,
        upload: CloudinaryUploadResult,
        generation_params: dict,
    ) -> dict:
        return {
            "scene_id": scene_id,
            "entity_name": entity_name,
            "asset_kind": asset_kind,
            "public_id": upload.public_id,
            "secure_url": upload.secure_url,
            "format": upload.format,
            "width": upload.width,
            "height": upload.height,
            "generation_params_json": generation_params,
            "revision": 1,
        }

    @staticmethod
    def _build_glb_generation_params(
        *,
        upload: CloudinaryUploadResult,
        preview_asset_kind: str | None,
        preview_persisted: bool,
        style: str,
        asset_role: str,
        entity_order: int | None = None,
        negative_prompt: str | None = None,
        builder_name: str = "textured_plane_glb",
        extra_params: dict | None = None,
    ) -> dict:
        params = {
            "builder": builder_name,
            "source_asset_type": "generated_preview_image",
            "source_asset_persisted": preview_persisted,
            "source_asset_storage": "cloudinary" if preview_persisted else "memory",
            "resource_type": upload.resource_type,
            "bytes_size": upload.bytes_size,
            "mime_type": "model/gltf-binary",
            "style": style,
            "asset_role": asset_role,
        }
        if preview_persisted and preview_asset_kind:
            params["source_asset_kind"] = preview_asset_kind
        if entity_order is not None:
            params["entity_order"] = entity_order
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if extra_params:
            params.update(extra_params)
        return params

    @staticmethod
    def _should_auto_layout_scene(entity_records: list[dict]) -> bool:
        if len(entity_records) <= 1:
            return False
        positions = {
            tuple(round(float(value), 4) for value in entity_record.get("position", [0.0, 0.0, 0.0]))
            for entity_record in entity_records
        }
        return len(positions) <= 1

    @staticmethod
    def _build_scene_planes(
        *,
        scene_preview_bytes: bytes,
        image_width: int,
        image_height: int,
        entity_previews: list[dict],
    ) -> list[ScenePlane]:
        background_scale = max(3.5, 1.8 + (len(entity_previews) * 0.9))
        scene_planes = [
            ScenePlane(
                name="scenario-background",
                image_bytes=scene_preview_bytes,
                image_width=image_width,
                image_height=image_height,
                translation=(0.0, 0.0, -1.6),
                scale=background_scale,
                animate=False,
            )
        ]

        auto_layout = AssetPipelineService._should_auto_layout_scene(entity_previews)
        center_index = (len(entity_previews) - 1) / 2.0 if entity_previews else 0.0

        for idx, entity_preview in enumerate(entity_previews):
            px, py, pz = entity_preview["position"]
            if auto_layout:
                px = (idx - center_index) * 1.25
                py = 0.0
                pz = -0.12 * abs(idx - center_index)

            scene_planes.append(
                ScenePlane(
                    name=f"entity-{AssetPipelineService._slugify(entity_preview['name'])}",
                    image_bytes=entity_preview["image_bytes"],
                    image_width=entity_preview["image_width"],
                    image_height=entity_preview["image_height"],
                    translation=(float(px), float(py), float(pz)),
                    scale=float(entity_preview["scale"]),
                    animate=True,
                    float_height=0.08 + (0.015 * (idx % 3)),
                    pulse_scale=0.035 + (0.01 * (idx % 2)),
                    animation_phase=(idx / max(len(entity_previews), 1)),
                )
            )

        return scene_planes

    def run(self, scene_id: str, request: AssetCreateRequest) -> PipelineResult:
        scene_title = self._resolve_scene_title(request)
        upload_previews = self._should_upload_previews(request)
        entity_names = [entity.name.strip() for entity in request.entities]
        image_format = (
            request.render_options.format
            if request.render_options and request.render_options.format
            else settings.default_output_format
        )
        width = request.render_options.width if request.render_options and request.render_options.width else settings.hf_image_width
        height = request.render_options.height if request.render_options and request.render_options.height else settings.hf_image_height
        style = request.render_options.style if request.render_options and request.render_options.style else settings.default_image_style
        negative_prompt = request.render_options.negative_prompt if request.render_options else None

        asset_records: list[dict] = []
        entity_records: list[dict] = []

        scene_prompt = self._build_background_prompt(request.scenario_text, style, entity_names)
        scene_negative_prompt = self._build_negative_prompt(
            negative_prompt,
            "isolated subject",
            "single hero character",
            "portrait",
            "close-up",
            "centered deity",
            *entity_names,
        )
        scene_preview_bytes = self.hf_image_client.generate_image(
            prompt=scene_prompt,
            width=width,
            height=height,
            negative_prompt=scene_negative_prompt,
        )
        scene_preview_upload: CloudinaryUploadResult | None = None
        if upload_previews:
            scene_preview_upload = self.cloudinary_client.upload_bytes(
                scene_preview_bytes,
                f"{settings.cloudinary_folder}/{scene_id}/scene/preview/rev_1",
                image_format,
                resource_type="image",
            )
        if scene_preview_upload:
            asset_records.append(
                self._build_db_asset_record(
                    scene_id=scene_id,
                    entity_name=None,
                    asset_kind="scene_preview_image",
                    upload=scene_preview_upload,
                    generation_params={
                        "prompt": scene_prompt,
                        "resource_type": scene_preview_upload.resource_type,
                        "bytes_size": scene_preview_upload.bytes_size,
                        "negative_prompt": scene_negative_prompt or "",
                        "style": style,
                    },
                )
            )

        entity_assets: list[dict] = []
        entity_previews: list[dict] = []
        for idx, entity in enumerate(request.entities):
            px = settings.default_position_x
            py = settings.default_position_y
            pz = settings.default_position_z
            if entity.position:
                px, py, pz = entity.position

            scale = float(entity.scale if entity.scale is not None else settings.default_scale)
            entity_slug = self._slugify(entity.name)
            other_entity_names = [name for name in entity_names if name.lower() != entity.name.strip().lower()]
            entity_prompt = self._build_entity_prompt(
                entity.name,
                request.scenario_text,
                style,
                other_entity_names,
            )
            entity_negative_prompt = self._build_negative_prompt(
                negative_prompt,
                "multiple subjects",
                "extra characters",
                "background scenery",
                "landscape",
                "full scene",
                "text",
                "watermark",
                *other_entity_names,
            )

            entity_preview_bytes = self.hf_image_client.generate_image(
                prompt=entity_prompt,
                width=width,
                height=height,
                negative_prompt=entity_negative_prompt,
            )
            entity_previews.append(
                {
                    "name": entity.name,
                    "image_bytes": entity_preview_bytes,
                    "image_width": width,
                    "image_height": height,
                    "position": [px, py, pz],
                    "scale": scale,
                }
            )
            entity_preview_upload: CloudinaryUploadResult | None = None
            if upload_previews:
                entity_preview_upload = self.cloudinary_client.upload_bytes(
                    entity_preview_bytes,
                    f"{settings.cloudinary_folder}/{scene_id}/entities/{entity_slug}/preview/rev_1",
                    image_format,
                    resource_type="image",
                )
            entity_glb_bytes = glb_builder_service.build_textured_plane_glb(
                entity_preview_bytes,
                image_width=width,
                image_height=height,
            )
            entity_glb_upload = self.cloudinary_client.upload_bytes(
                entity_glb_bytes,
                f"{settings.cloudinary_folder}/{scene_id}/entities/{entity_slug}/model/rev_1",
                settings.glb_output_format,
                resource_type="raw",
            )

            entity_records.append(
                {
                    "order": idx,
                    "name": entity.name,
                    "position": [px, py, pz],
                    "scale": scale,
                }
            )
            entity_assets.append(
                {
                    "name": entity.name,
                    "position": [px, py, pz],
                    "scale": scale,
                    "preview_image": self._build_asset_file(entity_preview_upload) if entity_preview_upload else None,
                    "glb_model": self._build_asset_file(entity_glb_upload),
                }
            )
            if entity_preview_upload:
                asset_records.append(
                    self._build_db_asset_record(
                        scene_id=scene_id,
                        entity_name=entity.name,
                        asset_kind="entity_preview_image",
                        upload=entity_preview_upload,
                        generation_params={
                            "prompt": entity_prompt,
                            "resource_type": entity_preview_upload.resource_type,
                            "bytes_size": entity_preview_upload.bytes_size,
                            "negative_prompt": entity_negative_prompt or "",
                            "style": style,
                            "entity_order": idx,
                        },
                    )
                )
            asset_records.append(
                self._build_db_asset_record(
                    scene_id=scene_id,
                    entity_name=entity.name,
                    asset_kind="entity_glb_model",
                    upload=entity_glb_upload,
                    generation_params=self._build_glb_generation_params(
                        upload=entity_glb_upload,
                        preview_asset_kind="entity_preview_image",
                        preview_persisted=upload_previews,
                        style=style,
                        asset_role="entity",
                        entity_order=idx,
                        negative_prompt=entity_negative_prompt,
                    ),
                )
            )

        scene_glb_bytes = glb_builder_service.build_animated_scene_glb(
            self._build_scene_planes(
                scene_preview_bytes=scene_preview_bytes,
                image_width=width,
                image_height=height,
                entity_previews=entity_previews,
            )
        )
        scene_glb_upload = self.cloudinary_client.upload_bytes(
            scene_glb_bytes,
            f"{settings.cloudinary_folder}/{scene_id}/scene/model/rev_1",
            settings.glb_output_format,
            resource_type="raw",
        )
        scene_assets = {
            "preview_image": self._build_asset_file(scene_preview_upload) if scene_preview_upload else None,
            "glb_model": self._build_asset_file(scene_glb_upload),
        }
        asset_records.append(
            self._build_db_asset_record(
                scene_id=scene_id,
                entity_name=None,
                asset_kind="scene_glb_model",
                upload=scene_glb_upload,
                generation_params=self._build_glb_generation_params(
                    upload=scene_glb_upload,
                    preview_asset_kind=None,
                    preview_persisted=upload_previews,
                    style=style,
                    asset_role="scenario",
                    negative_prompt=scene_negative_prompt,
                    builder_name="animated_scene_glb",
                    extra_params={
                        "source_asset_type": "generated_preview_images",
                        "entity_count": len(entity_previews),
                        "contains_background": True,
                        "contains_entity_glbs": True,
                    },
                ),
            )
        )

        response_payload = {
            "scene_id": scene_id,
            "status": "completed",
            "scene_title": scene_title,
            "scenario_text": request.scenario_text,
            "assets": {
                "scene": scene_assets,
                "entities": entity_assets,
            },
        }

        return PipelineResult(
            scene_id=scene_id,
            response_payload=response_payload,
            entity_records=entity_records,
            asset_records=asset_records,
        )


asset_pipeline_service = AssetPipelineService()
