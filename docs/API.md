# API Documentation

Base path: `/api/v1`

Auth:
- Protected routes require header: `token: <INTERNAL_TOKEN>`

## 1. Health

### `GET /health`

Response `200`:

```json
{
  "status": "ok"
}
```

## 2. Create Scene Assets

### `POST /scenes/assets?mode=sync|async`

Request body:

```json
{
  "request_id": "req_12345678",
  "scenario_text": "A floating market on Mars where robots and humans trade memories.",
  "entities": [
    "Memory Merchant",
    {
      "name": "Drone Porter",
      "position": [1.5, 0, -0.5],
      "scale": 0.9
    }
  ],
  "render_options": {
    "style": "cinematic 3d render",
    "format": "png",
    "width": 1024,
    "height": 1024,
    "negative_prompt": "blurry, low quality",
    "include_preview_assets": false
  }
}
```

Validation rules:
- `request_id`: optional, min 8, max 128 chars.
- `scene_title`: optional, max 200 chars.
- `entities`: required list, min 1 item.
- Entity items may be either raw strings or objects with `name`, optional `position`, and optional `scale`.
- Entity names must be unique (case-insensitive trimmed comparison).
- `render_options.format`: one of `png|jpg|webp`.
- `render_options.include_preview_assets`: optional debug/admin flag. Preview uploads are honored only when the service runs in debug mode or the server explicitly allows preview uploads.
- `mode`: `sync` or `async`.

### Sync mode response

Response `200` (`SceneAssetResponse`):

```json
{
  "scene_id": "scn_abc123...",
  "status": "completed",
  "scene_title": "A floating market on Mars where robots and humans trade memories.",
  "scenario_text": "...",
  "assets": {
    "scene": {
      "preview_image": null,
      "glb_model": {
        "url": "https://res.cloudinary.com/...",
        "public_id": "whatifverse/scenes/scn_x/scene/model/rev_1",
        "format": "glb",
        "resource_type": "raw",
        "bytes_size": 231908
      }
    },
    "entities": [
      {
        "name": "Memory Merchant",
        "position": [0, 0, 0],
        "scale": 1.2,
        "preview_image": null,
        "glb_model": {
          "url": "https://res.cloudinary.com/...",
          "public_id": "whatifverse/scenes/scn_x/entities/memory-merchant/model/rev_1",
          "format": "glb",
          "resource_type": "raw",
          "bytes_size": 190225
        }
      }
    ]
  },
  "idempotent_replay": false
}
```

Notes:

- `glb_model` is the primary V2 asset returned to the frontend.
- `preview_image` is `null` by default because preview PNGs are not uploaded in normal mode.
- `preview_image` becomes available only when preview uploads are explicitly enabled for debug/admin workflows.
- The current V2 GLB builder wraps the generated preview into a textured upright plane so it can be placed in AR on a flat surface.

### Async mode response

Response `200` (`JobAcceptedResponse`):

```json
{
  "job_id": "job_abc123...",
  "status": "queued",
  "scene_id": "scn_abc123..."
}
```

Background worker transitions the job from `queued -> processing -> completed/failed`.

## 3. Get Scene

### `GET /scenes/{scene_id}`

Response `200`: same shape as `SceneAssetResponse`.

Response `404`:

```json
{
  "error": {
    "code": "SCENE_NOT_FOUND",
    "message": "scene_id was not found",
    "timestamp": "2026-..."
  }
}
```

## 4. Get Job

### `GET /jobs/{job_id}`

Response `200` (`JobStatusResponse`):

```json
{
  "job_id": "job_abc123...",
  "status": "processing",
  "scene_id": "scn_abc123...",
  "result": null,
  "error": null
}
```

Completed example:

```json
{
  "job_id": "job_abc123...",
  "status": "completed",
  "scene_id": "scn_abc123...",
  "result": {
    "scene_id": "scn_abc123...",
    "status": "completed",
    "scene_title": "...",
    "scenario_text": "...",
    "assets": {
      "scene": {
        "preview_image": null,
        "glb_model": {
          "url": "https://res.cloudinary.com/...",
          "public_id": "whatifverse/scenes/scn_x/scene/model/rev_1",
          "format": "glb",
          "resource_type": "raw",
          "bytes_size": 231908
        }
      },
      "entities": []
    },
    "idempotent_replay": false
  },
  "error": null
}
```

Failed example:

```json
{
  "job_id": "job_abc123...",
  "status": "failed",
  "scene_id": "scn_abc123...",
  "result": null,
  "error": {
    "code": "ASSET_GENERATION_FAILED",
    "message": "Failed to generate GLB assets",
    "details": "..."
  }
}
```

Response `404`:

```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "job_id was not found"
  }
}
```

## 5. Idempotency Behavior

If `request_id` is provided:

- First request inserts idempotency record with status `processing`.
- Same `request_id` + same payload:
  - If still processing -> `409 IDEMPOTENCY_REQUEST_IN_PROGRESS`
  - If completed -> replay prior response with `idempotent_replay: true`
- Same `request_id` + different payload hash -> `409 IDEMPOTENCY_KEY_PAYLOAD_MISMATCH`
- If generation fails, the idempotency record is cleared so the caller can retry with the same `request_id`.

## 6. Common Error Codes

- `INVALID_INTERNAL_TOKEN` (401)
- `MAX_ENTITIES_EXCEEDED` (400)
- `IDEMPOTENCY_KEY_PAYLOAD_MISMATCH` (409)
- `IDEMPOTENCY_REQUEST_IN_PROGRESS` (409)
- `SCENE_NOT_FOUND` (404)
- `JOB_NOT_FOUND` (404)
- `VALIDATION_ERROR` (422)
- `INTERNAL_SERVER_ERROR` (500)
