# WhatIfVerse Image Service

FastAPI service that generates scene images and entity images from scenario text using Hugging Face inference, uploads assets to Cloudinary, and persists scene/job/idempotency state in Neon Postgres.

## Features

- Token-protected API (`token` header required).
- Single create endpoint with `sync` and `async` modes.
- Idempotency with `request_id + payload_hash`.
- Real image generation via Hugging Face router inference endpoint.
- Real image hosting via Cloudinary.
- DB-backed state for:
  - scenes
  - jobs
  - idempotency records

## Current API

- `GET /api/v1/health`
- `POST /api/v1/scenes/assets?mode=sync|async`
- `GET /api/v1/scenes/{scene_id}`
- `GET /api/v1/jobs/{job_id}`

Detailed request/response examples: see [docs/API.md](docs/API.md).

## Quick Start (Windows)

1. Create and activate venv

```powershell
python -m venv environment
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\environment\Scripts\Activate.ps1)
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

3. Configure env

Create `.env` in project root and set at least:

```env
INTERNAL_TOKEN=your_internal_token
HF_TOKEN=your_hf_token
HF_TEXT_TO_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
CLOUDINARY_CLOUD_NAME=your_cloud
CLOUDINARY_API_KEY=your_key
CLOUDINARY_API_SECRET=your_secret
DATABASE_URL=postgresql+psycopg2://...
```

Note:
- Env parsing is case-insensitive.
- Unknown env keys are ignored.

4. Run API

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

5. Verify

```powershell
curl http://127.0.0.1:8001/api/v1/health
```

## DB Integration Status

Fully DB-backed now:

- `idempotency_records` table is used for request replay and mismatch checks.
- `jobs` table is used for async job state polling.
- `scenes` table stores final response payload (`response_json`).

Startup behavior:

- If `DATABASE_URL` is set, app startup runs DB connectivity check and `create_all`.

More details: [docs/DB_INTEGRATION.md](docs/DB_INTEGRATION.md)

## Project Docs

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- API contracts: [docs/API.md](docs/API.md)
- Environment and setup: [docs/SETUP_AND_ENV.md](docs/SETUP_AND_ENV.md)
- DB behavior and idempotency semantics: [docs/DB_INTEGRATION.md](docs/DB_INTEGRATION.md)
- Agent onboarding + workflows: [agent.md](agent.md), [agent.d.md](agent.d.md)

## Security

- All protected routes require `token` header matching `INTERNAL_TOKEN`.
- Never commit `.env`.
- Rotate tokens/keys immediately if leaked.
