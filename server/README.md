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
| `IMAGE_EDIT_MODEL_BACKEND` | `stub` | Pipeline backend: `stub` or `sana` |
| `IMAGE_EDIT_SANA_MODEL_ID` | `Efficient-Large-Model/Sana_1600M_1024px_diffusers` | HuggingFace model id for Sana |
| `IMAGE_EDIT_SANA_DEVICE` | `cpu` | Inference device: `cpu`, `cuda`, `mps` |
| `IMAGE_EDIT_SANA_TORCH_DTYPE` | `float32` | Torch dtype: `float32`, `float16`, `bfloat16` |
| `IMAGE_EDIT_SANA_NUM_INFERENCE_STEPS` | `20` | Denoising steps |
| `IMAGE_EDIT_SANA_OUTPUT_WIDTH` | `1024` | Output image width in pixels |
| `IMAGE_EDIT_SANA_OUTPUT_HEIGHT` | `1024` | Output image height in pixels |

## Running with Sana

Install ML dependencies (skip for stub/test runs):

```bash
uv sync --group ml
```

For CUDA inference, replace the torch wheel with the appropriate CUDA build:

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Pre-download the model (one-time, ~6 GB):

```bash
uv run python -c "from diffusers import SanaPipeline; SanaPipeline.from_pretrained('Efficient-Large-Model/Sana_1600M_1024px_diffusers')"
```

Start the server with Sana on CPU (slow, useful for smoke testing):

```bash
IMAGE_EDIT_MODEL_BACKEND=sana IMAGE_EDIT_SANA_DEVICE=cpu \
  uv run uvicorn image_edit_server.main:app --reload --port 8000
```

For GPU (recommended):

```bash
IMAGE_EDIT_MODEL_BACKEND=sana IMAGE_EDIT_SANA_DEVICE=cuda IMAGE_EDIT_SANA_TORCH_DTYPE=float16 \
  uv run uvicorn image_edit_server.main:app --port 8000
```

## Tests

```bash
uv run pytest
```
