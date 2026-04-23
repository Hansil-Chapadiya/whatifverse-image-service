from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "whatifverse-image-service"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8001
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    internal_token: str = ""
    cors_allowed_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://whatifverse.vercel.app"
    )

    ai_service_base_url: str = ""
    ai_service_token: str = ""
    ai_generate_endpoint: str = "/api/v1/ai/generate"
    ai_entities_endpoint: str = "/api/v1/ai/entities"
    ai_request_timeout: int = 60

    hf_token: str = ""
    hf_provider: str = ""
    hf_text_to_image_model: str = ""
    hf_image_width: int = 1024
    hf_image_height: int = 1024
    hf_num_inference_steps: int = 4
    hf_guidance_scale: float = 3.5
    hf_negative_prompt: str = ""

    enable_glb_pipeline: bool = False
    hf_image_to_3d_model: str = ""
    glb_output_format: str = "glb"
    persist_preview_assets: bool = False
    allow_preview_asset_uploads: bool = False

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "whatifverse/scenes"
    cloudinary_secure: bool = True

    database_url: str = ""
    db_echo: bool = False
    scene_cache_max_items: int = 256

    default_image_style: str = "cinematic 3d render"
    default_output_format: str = "png"
    max_entities_per_scene: int = 5
    default_scale: float = 1.0
    default_position_x: float = 0.0
    default_position_y: float = 0.0
    default_position_z: float = 0.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.cors_allowed_origins.split(",") if origin.strip()]
        if origins == ["*"]:
            return ["*"]
        return origins


settings = Settings()
