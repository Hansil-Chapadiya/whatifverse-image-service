from dataclasses import dataclass
from io import BytesIO

import cloudinary
import cloudinary.uploader

from app.core.config import settings


@dataclass
class CloudinaryUploadResult:
    secure_url: str
    public_id: str
    format: str
    width: int
    height: int


class CloudinaryClient:
    def __init__(self) -> None:
        if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
            raise RuntimeError("Cloudinary credentials are required")

        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=settings.cloudinary_secure,
        )

    def upload_bytes(self, image_bytes: bytes, public_id: str, image_format: str) -> CloudinaryUploadResult:
        upload_result = cloudinary.uploader.upload(
            BytesIO(image_bytes),
            public_id=public_id,
            resource_type="image",
            overwrite=True,
            format=image_format,
        )

        secure_url = str(upload_result.get("secure_url", ""))
        result_public_id = str(upload_result.get("public_id", public_id))
        result_format = str(upload_result.get("format", image_format))
        width = int(upload_result.get("width", 0))
        height = int(upload_result.get("height", 0))

        if not secure_url:
            raise RuntimeError("Cloudinary upload did not return secure_url")

        return CloudinaryUploadResult(
            secure_url=secure_url,
            public_id=result_public_id,
            format=result_format,
            width=width,
            height=height,
        )
