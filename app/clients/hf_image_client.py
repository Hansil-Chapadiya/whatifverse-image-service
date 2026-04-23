import httpx

from app.core.config import settings


class HFImageClient:
    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN is required for image generation")
        if not settings.hf_text_to_image_model:
            raise RuntimeError("HF_TEXT_TO_IMAGE_MODEL is required for image generation")

        self._inference_endpoint = f"https://router.huggingface.co/hf-inference/models/{settings.hf_text_to_image_model}"
        self._headers = {
            "Authorization": f"Bearer {settings.hf_token}",
            "Content-Type": "application/json",
        }

    def generate_image(
        self,
        prompt: str,
        width: int,
        height: int,
        negative_prompt: str | None,
    ) -> bytes:
        effective_negative = negative_prompt if negative_prompt is not None else settings.hf_negative_prompt

        inference_payload = {
            "inputs": prompt,
            "parameters": {
                "width": width,
                "height": height,
                "num_inference_steps": settings.hf_num_inference_steps,
                "guidance_scale": settings.hf_guidance_scale,
            },
            "options": {"wait_for_model": True},
        }
        if effective_negative:
            inference_payload["parameters"]["negative_prompt"] = effective_negative

        headers = {**self._headers, "Accept": "image/png"}

        with httpx.Client(timeout=settings.ai_request_timeout) as client:
            response = client.post(self._inference_endpoint, headers=headers, json=inference_payload)

        if response.status_code >= 400:
            detail = response.text
            try:
                error_body = response.json()
                if isinstance(error_body, dict) and "error" in error_body:
                    detail = str(error_body["error"])
            except Exception:
                pass
            raise RuntimeError(f"Hugging Face image generation failed: {response.status_code} {detail}")

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type:
            raise RuntimeError("Hugging Face response did not return image bytes")

        return response.content
