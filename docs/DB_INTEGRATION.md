# Database Integration Documentation

## Summary

Database integration is complete for operational state:

- Idempotency records are stored in DB.
- Async jobs are stored in DB.
- Scene final response payload is stored in DB.
- Scene entities are stored in normalized rows.
- GLB assets are stored in normalized rows.
- Preview-image assets are stored only when preview uploads are explicitly enabled.

## Tables

Defined in `app/db/models/asset_model.py`.

### `scenes`

Key fields:
- `id` (PK)
- `request_id` (unique, nullable)
- `payload_hash` (nullable)
- `status`
- `response_json` (JSONB)
- timestamps

### `jobs`

Key fields:
- `id` (PK)
- `scene_id`
- `status` (`queued|processing|completed|failed`)
- `result_json` (JSONB)
- timestamps

### `idempotency_records`

Key fields:
- `request_id` (PK)
- `payload_hash`
- `status` (`processing|completed`)
- `response_json` (JSONB)
- timestamps

## Runtime Behavior

## 1. Idempotency lifecycle

1. New request with `request_id` inserts `processing` row.
2. Duplicate request checks existing row:
   - Hash mismatch -> 409 payload mismatch.
   - No response yet -> 409 in progress.
   - Response present -> replay response.
3. On completion, row updates to `completed` with `response_json`.

## 2. Job lifecycle

1. Async submit creates `jobs` row with status `queued`.
2. Worker sets status `processing`.
3. Worker stores final payload in `result_json` and status `completed` (or `failed`).
4. Poll endpoint reads from DB.

## 3. Scene persistence

Final scene response payload is written to `scenes.response_json` and retrieved by scene GET endpoint.

Additionally:

- `scene_entities` stores entity name + transform metadata
- `assets` stores Cloudinary metadata for GLB files by default
- preview-image metadata is included only when preview uploads are enabled

## Startup Integration

`app/main.py` startup hook:

- checks DB connectivity
- runs `Base.metadata.create_all()`

This ensures tables exist before serving requests (when `DATABASE_URL` is configured).

## Verification Commands

```powershell
# import sanity
.\environment\Scripts\python.exe -c "from app.main import app; print('app_ok', len(app.routes))"

# db init and connection
.\environment\Scripts\python.exe -c "from app.db.session import check_db_connection, init_db; check_db_connection(); init_db(); print('db_init_ok')"
```

## Known Limitation

- Schema evolution is currently handled via `create_all`, not versioned migrations.
- The current V2 GLB output is a textured plane model, not a true generated 3D mesh.
- Recommended next steps:
  - wire Alembic migration history
  - replace the plane builder with a true image-to-3D or scene-to-3D pipeline when ready
