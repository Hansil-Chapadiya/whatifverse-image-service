# Agent Guide: WhatIfVerse Image Service

This file is the implementation-aware onboarding guide for human contributors and coding agents.

## 1. What This Service Does

This FastAPI service creates visual assets for a scene:

- Generates one scene image from `scene_title + scenario_text`
- Generates one image per entity
- Uploads all generated images to Cloudinary
- Returns structured scene payload
- Supports both sync and async generation modes

It also enforces idempotency and persists state in Postgres (Neon).

## 2. Current Endpoints

Base prefix: `/api/v1`

- `GET /health`
- `POST /scenes/assets?mode=sync|async`
- `GET /scenes/{scene_id}`
- `GET /jobs/{job_id}`

All routes except health are token-protected.

## 3. Authentication Contract

Header required on protected routes:

- `token: <INTERNAL_TOKEN>`

Validation lives in:

- `app/core/security.py`

On mismatch, API returns `401 INVALID_INTERNAL_TOKEN`.

## 4. Core Runtime Flow

### Sync mode

1. Validate payload.
2. Optional idempotency check via `request_id`.
3. Run pipeline:
   - HF image generation (bytes)
   - Cloudinary upload
4. Save scene payload in DB.
5. Save idempotency completion response.
6. Return final scene response.

### Async mode

1. Validate payload.
2. Optional idempotency check via `request_id`.
3. Create DB job record as `queued`.
4. Return `job_id` immediately.
5. Background task executes pipeline and writes final job result.

## 5. Idempotency Rules (Important)

If `request_id` is sent:

- Same `request_id` + different payload hash:
  - return `409 IDEMPOTENCY_KEY_PAYLOAD_MISMATCH`
- Same `request_id` + same hash while processing:
  - return `409 IDEMPOTENCY_REQUEST_IN_PROGRESS`
- Same `request_id` + same hash after completion:
  - replay previous response with `idempotent_replay=true`

Hash is canonical SHA256 over request payload excluding `request_id`.

## 6. Database Source of Truth

DB-backed state includes:

- scene payloads (`scenes.response_json`)
- async jobs (`jobs` table)
- idempotency records (`idempotency_records` table)

Main files:

- `app/db/models/asset_model.py`
- `app/db/session.py`
- `app/services/scene_store.py`
- `app/services/idempotency_service.py`

Startup behavior:

- If `DATABASE_URL` exists, app startup checks DB connectivity and runs `create_all`.

## 7. External Integrations

### Hugging Face

Used endpoint pattern:

- `https://router.huggingface.co/hf-inference/models/{HF_TEXT_TO_IMAGE_MODEL}`

Client file:

- `app/clients/hf_image_client.py`

### Cloudinary

Uploads image bytes and returns hosted URL metadata.

Client file:

- `app/clients/cloudinary_client.py`

## 8. Key Files by Responsibility

- App bootstrap: `app/main.py`
- Route orchestration: `app/api/v1/routes/assets.py`, `app/api/v1/routes/jobs.py`
- Business flow: `app/services/asset_pipeline_service.py`
- Persistence adapters: `app/services/scene_store.py`, `app/services/idempotency_service.py`
- Schemas: `app/schemas/requests/asset_request.py`, `app/schemas/responses/asset_response.py`
- Settings: `app/core/config.py`

## 9. Required Env Keys for Full Runtime

- `INTERNAL_TOKEN`
- `HF_TOKEN`
- `HF_TEXT_TO_IMAGE_MODEL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `DATABASE_URL`

Useful optional keys:

- `HF_IMAGE_WIDTH`, `HF_IMAGE_HEIGHT`
- `HF_NUM_INFERENCE_STEPS`, `HF_GUIDANCE_SCALE`, `HF_NEGATIVE_PROMPT`
- `DEFAULT_IMAGE_STYLE`, `MAX_ENTITIES_PER_SCENE`

## 10. Safe Change Guidelines for Agents

1. Preserve response schema contracts in route handlers.
2. Do not weaken idempotency mismatch semantics.
3. Keep job polling backward compatible (`queued|processing|completed|failed`).
4. Never hardcode secrets in code/docs.
5. Prefer adding migration tooling (Alembic) before schema refactors.

## 11. Recommended Next Improvements

- Add Alembic migrations (currently `create_all` only).
- Add route-level integration tests for async polling path.
- Persist full per-asset rows (`AssetModel`) if long-term analytics/audit is required.
- Add structured logging around external call latency and failures.
