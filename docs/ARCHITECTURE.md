# Architecture Documentation

## Overview

The service is structured as a layered FastAPI application:

1. API routes (transport + validation orchestration)
2. Services (business flow)
3. Clients (external integrations)
4. Persistence layer (SQLAlchemy + Postgres)

## Request Flow

### Scene asset creation (sync)

1. `POST /api/v1/scenes/assets?mode=sync`
2. Token validation dependency runs.
3. Payload validated with Pydantic.
4. Optional idempotency check (`request_id`).
5. `AssetPipelineService.run()`:
   - Build scene prompt.
   - Generate scene image bytes via Hugging Face.
   - Upload to Cloudinary.
   - Generate and upload each entity image.
6. Persist final scene payload in DB.
7. Persist idempotency completion state.
8. Return `SceneAssetResponse`.

### Scene asset creation (async)

1. `POST /api/v1/scenes/assets?mode=async`
2. Validate + idempotency check.
3. Insert queued job row.
4. Return `job_id` immediately.
5. Background task runs same pipeline.
6. Update job status/result in DB.

### Job polling

1. `GET /api/v1/jobs/{job_id}`
2. Read job state from DB.
3. Return status with optional final result.

## Components

### API Layer

- `app/api/v1/routes/assets.py`
- `app/api/v1/routes/jobs.py`
- `app/api/v1/routes/health.py`

Responsibilities:
- HTTP status code contract
- idempotency error semantics
- sync vs async mode branching

### Service Layer

- `app/services/asset_pipeline_service.py`
- `app/services/idempotency_service.py`
- `app/services/scene_store.py`

Responsibilities:
- generation/upload orchestration
- idempotency hash + record lifecycle
- scene/job persistence abstraction

### Client Layer

- `app/clients/hf_image_client.py`
- `app/clients/cloudinary_client.py`

Responsibilities:
- external API payload format
- integration-specific error normalization

### Data Layer

- `app/db/models/asset_model.py`
- `app/db/session.py`

Responsibilities:
- SQLAlchemy models
- DB engine/session setup
- startup connection check + create_all

## Persistence Strategy

DB is source of truth for:

- scenes (`scenes.response_json`)
- jobs (`jobs.status`, `jobs.result_json`)
- idempotency (`idempotency_records`)

An in-process scene cache exists for quick same-process reads, but DB persistence guarantees recovery across restarts.

## External Dependencies

- Hugging Face router inference endpoint:
  - `https://router.huggingface.co/hf-inference/models/{HF_TEXT_TO_IMAGE_MODEL}`
- Cloudinary upload API
- Neon Postgres (via `DATABASE_URL`)

## Startup Lifecycle

On app startup:

- If `DATABASE_URL` present:
  - DB connection check (`SELECT 1`)
  - model metadata create (`Base.metadata.create_all`)

If `DATABASE_URL` missing, DB-backed methods no-op and runtime behavior degrades for persistence-dependent flows.
