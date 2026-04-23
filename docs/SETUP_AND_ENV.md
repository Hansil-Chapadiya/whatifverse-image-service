# Setup and Environment Documentation

## Prerequisites

- Python 3.10+
- Virtual environment tooling
- Access credentials for:
  - Hugging Face
  - Cloudinary
  - Neon/Postgres

## Install

```powershell
python -m venv environment
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\environment\Scripts\Activate.ps1)
pip install -r requirements.txt
```

## Minimal `.env` for Full Functionality

```env
APP_NAME=whatifverse-image-service
API_V1_PREFIX=/api/v1
DEBUG=true

INTERNAL_TOKEN=replace_me

HF_TOKEN=replace_me
HF_TEXT_TO_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
HF_IMAGE_WIDTH=1024
HF_IMAGE_HEIGHT=1024
HF_NUM_INFERENCE_STEPS=4
HF_GUIDANCE_SCALE=3.5
HF_NEGATIVE_PROMPT=

CLOUDINARY_CLOUD_NAME=replace_me
CLOUDINARY_API_KEY=replace_me
CLOUDINARY_API_SECRET=replace_me
CLOUDINARY_FOLDER=whatifverse/scenes
CLOUDINARY_SECURE=true

DATABASE_URL=postgresql+psycopg2://user:password@host/dbname
DB_ECHO=false

MAX_ENTITIES_PER_SCENE=5
DEFAULT_IMAGE_STYLE=cinematic 3d render
DEFAULT_OUTPUT_FORMAT=png
DEFAULT_SCALE=1.0
DEFAULT_POSITION_X=0.0
DEFAULT_POSITION_Y=0.0
DEFAULT_POSITION_Z=0.0
```

## Important Config Notes

- Settings are case-insensitive.
- Unknown `.env` keys are ignored (`extra=ignore`).
- `INTERNAL_TOKEN` is required for protected endpoints.
- `HF_TOKEN` and `HF_TEXT_TO_IMAGE_MODEL` are required for generation.
- Cloudinary credentials are required for upload.
- `DATABASE_URL` is required for persistent jobs/idempotency.

## Run

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Health Check

```powershell
curl http://127.0.0.1:8001/api/v1/health
```

## Common Configuration Failures

- Missing HF credentials -> runtime error from `HFImageClient`.
- Missing Cloudinary credentials -> runtime error from `CloudinaryClient`.
- Wrong token header -> 401 `INVALID_INTERNAL_TOKEN`.
- DB URL missing/invalid -> startup DB check or persistence calls fail.
