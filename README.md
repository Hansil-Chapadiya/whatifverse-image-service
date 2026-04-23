# WhatIfVerse Image Service

FastAPI service that accepts scenario text plus extracted entities, generates preview renders with Hugging Face, converts those renders into simple GLB models, uploads GLB assets to Cloudinary, and persists scene/job/idempotency state in Neon Postgres.

## Features

- Token-protected API (`token` header required)
- Single create endpoint with `sync` and `async` modes
- Accepts AI-service friendly input: `scenario_text + entities`
- Generates preview images via Hugging Face
- Builds V2 GLB assets as textured planes for AR placement
- Uploads GLB files to Cloudinary by default
- Keeps preview images in memory and only uploads them when explicitly allowed for debugging/admin workflows
- DB-backed state for:
  - scenes
  - scene entities
  - assets
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

## V2 Output Model

Each completed scene returns:

- one animated scene GLB model for direct AR placement
- per-entity GLB models as secondary assets

Optional debug/admin mode can also include uploaded preview images.

The current GLB builder produces:

- per-entity textured upright-plane GLBs
- one merged animated scene GLB that combines the background and entities into a single AR-ready model

This is a practical V2 step for AR placement while a true image-to-3D pipeline is still being developed.

## DB Integration Status

DB-backed now:

- `idempotency_records` table is used for request replay and mismatch checks
- `jobs` table is used for async job state polling
- `scenes` table stores the final response payload (`response_json`)
- `scene_entities` stores normalized entity rows
- `assets` stores normalized GLB asset rows by default
- preview-image rows are stored only when preview uploads are explicitly enabled

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
