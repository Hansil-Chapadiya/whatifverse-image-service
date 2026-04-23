from dataclasses import dataclass
from uuid import uuid4

from app.clients.cloudinary_client import CloudinaryClient
from app.clients.hf_image_client import HFImageClient
from app.core.config import settings
from app.schemas.requests.asset_request import AssetCreateRequest


@dataclass
class PipelineResult:
    scene_id: str
    scene_title: str
    scenario_text: str
    scene_asset: dict
    entity_assets: list[dict]


class AssetPipelineService:
    def __init__(self) -> None:
        self.hf_image_client = HFImageClient()
        self.cloudinary_client = CloudinaryClient()

    @staticmethod
    def _build_scene_prompt(scene_title: str, scenario_text: str, style: str) -> str:
        return (
            f"Scene title: {scene_title}. "
            f"Scenario: {scenario_text}. "
            f"Create a high quality visual scene in style: {style}."
        )

    @staticmethod
    def _build_entity_prompt(entity_name: str, scenario_text: str, style: str) -> str:
        return (
            f"Entity: {entity_name}. "
            f"Scenario context: {scenario_text}. "
            f"Generate a clean isolated visual asset for this entity in style: {style}."
        )

    def run(self, request: AssetCreateRequest) -> PipelineResult:
        scene_id = f"scn_{uuid4().hex[:12]}"
        image_format = (request.render_options.format if request.render_options and request.render_options.format else settings.default_output_format)
        width = request.render_options.width if request.render_options and request.render_options.width else settings.hf_image_width
        height = request.render_options.height if request.render_options and request.render_options.height else settings.hf_image_height
        style = request.render_options.style if request.render_options and request.render_options.style else settings.default_image_style
        negative_prompt = request.render_options.negative_prompt if request.render_options else None

        scene_prompt = self._build_scene_prompt(request.scene_title, request.scenario_text, style)
        scene_image_bytes = self.hf_image_client.generate_image(
            prompt=scene_prompt,
            width=width,
            height=height,
            negative_prompt=negative_prompt,
        )

        scene_public_id = f"{settings.cloudinary_folder}/{scene_id}/scene/rev_1"
        scene_upload = self.cloudinary_client.upload_bytes(scene_image_bytes, scene_public_id, image_format)

        entity_assets: list[dict] = []
        for idx, entity in enumerate(request.entities):
            px = settings.default_position_x
            py = settings.default_position_y
            pz = settings.default_position_z
            if entity.position:
                px, py, pz = entity.position

            scale = entity.scale if entity.scale is not None else settings.default_scale
            entity_slug = entity.name.strip().lower().replace(" ", "-")
            entity_public_id = f"{settings.cloudinary_folder}/{scene_id}/entities/{entity_slug}/rev_1"

            entity_prompt = self._build_entity_prompt(entity.name, request.scenario_text, style)
            entity_image_bytes = self.hf_image_client.generate_image(
                prompt=entity_prompt,
                width=width,
                height=height,
                negative_prompt=negative_prompt,
            )
            entity_upload = self.cloudinary_client.upload_bytes(entity_image_bytes, entity_public_id, image_format)

            entity_assets.append(
                {
                    "order": idx,
                    "name": entity.name,
                    "image_url": entity_upload.secure_url,
                    "public_id": entity_upload.public_id,
                    "position": [px, py, pz],
                    "scale": float(scale),
                }
            )

        return PipelineResult(
            scene_id=scene_id,
            scene_title=request.scene_title,
            scenario_text=request.scenario_text,
            scene_asset={
                "image_url": scene_upload.secure_url,
                "public_id": scene_upload.public_id,
                "format": scene_upload.format,
                "width": scene_upload.width,
                "height": scene_upload.height,
            },
            entity_assets=entity_assets,
        )


asset_pipeline_service = AssetPipelineService()
