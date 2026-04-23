# Database Integration Documentation

## Summary

Database integration is complete for operational state:

- Idempotency records are stored in DB.
- Async jobs are stored in DB.
- Scene final response payload is stored in DB.

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
- Recommended next step: wire Alembic migration history for production-safe schema changes.
