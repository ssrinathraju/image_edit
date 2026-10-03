# image-edit server

FastAPI backend for the image_edit project. Accepts reference face images and a prompt, runs an async generation pipeline, and returns the generated image.

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn image_edit_server.main:app --reload --port 8000
```

OpenAPI schema: http://localhost:8000/openapi.json

## Submit a generation job

```bash
curl -X POST http://localhost:8000/generations \
  -F "prompt=a family hiking in the Alps at sunset" \
  -F "faces=@/path/to/face1.jpg" \
  -F "faces=@/path/to/face2.jpg"
# → {"job_id": "01HE..."}
```

## Poll for status

```bash
curl http://localhost:8000/generations/<job_id>
# → {"job_id": "...", "status": "queued"|"running"|"succeeded"|"failed",
#    "result_url": "/images/<job_id>.png"}
```

## Download the result

```bash
curl http://localhost:8000/images/<job_id>.png -o result.png
```

## Config (environment variables)

| Variable | Default | Description |
|---|---|---|
| `IMAGE_EDIT_STORAGE_ROOT` | `./storage` | Root directory for inputs and outputs |
| `IMAGE_EDIT_MAX_FACES` | `4` | Maximum number of reference faces per request |
| `IMAGE_EDIT_MIN_FACES` | `1` | Minimum number of reference faces per request |
| `IMAGE_EDIT_MAX_PROMPT_CHARS` | `500` | Maximum prompt length in characters |
| `IMAGE_EDIT_MAX_UPLOAD_BYTES` | `10485760` | Maximum size per face upload (bytes) |
| `IMAGE_EDIT_JOB_CONCURRENCY` | `1` | Number of parallel worker coroutines |
| `IMAGE_EDIT_OUTPUT_RETENTION_HOURS` | `24` | How long outputs are kept (enforcement deferred) |
| `IMAGE_EDIT_ACCEPTED_IMAGE_TYPES` | `image/jpeg,image/png,image/webp` | Accepted MIME types for face uploads |

## Tests

```bash
uv run pytest
```
