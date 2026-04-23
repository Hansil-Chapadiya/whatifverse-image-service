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
  "scene_title": "Neon Mars Bazaar",
  "scenario_text": "A floating market on Mars where robots and humans trade memories.",
  "entities": [
    {
      "name": "Memory Merchant",
      "position": [0, 0, 0],
      "scale": 1.2
    },
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
    "negative_prompt": "blurry, low quality"
  }
}
```

Validation rules:
- `request_id`: optional, min 8, max 128 chars.
- `scene_title`: required, max 200 chars.
- `entities`: required list, min 1 item.
- Entity names must be unique (case-insensitive trimmed comparison).
- `render_options.format`: one of `png|jpg|webp`.
- `mode`: `sync` or `async`.

### Sync mode response

Response `200` (`SceneAssetResponse`):

```json
{
  "scene_id": "scn_abc123...",
  "status": "completed",
  "scene_title": "Neon Mars Bazaar",
  "scenario_text": "...",
  "assets": {
    "scene_image": {
      "image_url": "https://res.cloudinary.com/...",
      "public_id": "whatifverse/scenes/scn_x/scene/rev_1",
      "format": "png",
      "width": 1024,
      "height": 1024
    },
    "entities": [
      {
        "name": "Memory Merchant",
        "image_url": "https://res.cloudinary.com/...",
        "public_id": "whatifverse/scenes/scn_x/entities/memory-merchant/rev_1",
        "position": [0, 0, 0],
        "scale": 1.2
      }
    ]
  },
  "idempotent_replay": false
}
```

### Async mode response

Response `200` (`JobAcceptedResponse`):

```json
{
  "job_id": "job_abc123...",
  "status": "queued",
  "scene_id": "scn_temp123..."
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
  "scene_id": "scn_temp123...",
  "result": null
}
```

When completed, `result` contains full `SceneAssetResponse`.

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

## 6. Common Error Codes

- `INVALID_INTERNAL_TOKEN` (401)
- `MAX_ENTITIES_EXCEEDED` (400)
- `IDEMPOTENCY_KEY_PAYLOAD_MISMATCH` (409)
- `IDEMPOTENCY_REQUEST_IN_PROGRESS` (409)
- `SCENE_NOT_FOUND` (404)
- `JOB_NOT_FOUND` (404)
- `VALIDATION_ERROR` (422)
- `INTERNAL_SERVER_ERROR` (500)
