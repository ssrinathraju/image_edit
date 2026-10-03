# Design

## Context

See `proposal.md — Why` for motivation. Current state: `main.py` hardcodes `StubPipeline` on line 20. The `GenerationPipeline` Protocol (`core/pipeline.py`) is already the abstraction point — adding a new backend is purely additive.

## Goals / Non-Goals

**Goals:**
- Add `SanaPipeline` satisfying the `GenerationPipeline` Protocol
- Replace the hardcoded stub with a config-driven factory in `main.py`
- Keep `StubPipeline` available for tests and CI (`MODEL_BACKEND=stub` default)
- Run inference in a threadpool so the async event loop stays unblocked

**Non-Goals:**
- Face identity conditioning (deferred to a future change)
- Multi-GPU or batched inference
- Model caching across server restarts (HuggingFace `from_pretrained` handles disk cache)
- CUDA installation automation (user installs the right torch wheel manually)

## Decisions

### 1. Pipeline factory inline in `main.py`

A separate `pipeline_factory.py` module is premature for two backends. The factory is a short `if/elif` block inside `create_app`. If a third backend arrives, extract then.

### 2. Model loaded once at startup (lifespan), not per-request

Loading Sana takes several seconds and consumes several GB of RAM. Load it once in the `lifespan` context manager before workers start. Shutdown cancels workers first, then the model reference is released.

### 3. Blocking inference runs via `asyncio.to_thread`

`diffusers` inference is synchronous. Wrapping with `asyncio.to_thread` keeps the event loop free for polling requests while a job runs. This works correctly with the existing single-worker concurrency model (`JOB_CONCURRENCY=1`).

### 4. `MODEL_BACKEND` env var selects the pipeline

| Value | Pipeline | ML deps required? |
|---|---|---|
| `stub` (default) | `StubPipeline` | No |
| `sana` | `SanaPipeline` | Yes |

Default is `stub` so existing tests and CI pass without any ML install.

### 5. ML deps in an optional `[ml]` dependency group

`torch`, `diffusers`, `transformers`, `accelerate`, `sentencepiece`, `protobuf` are heavy and unnecessary for the stub path. They go in `[dependency-groups] ml = [...]` in `pyproject.toml`. Install with `uv sync --group ml` on the GPU box.

`torch` is listed as CPU-only (`torch`) in the group. For CUDA inference the user installs the appropriate CUDA wheel on top: `uv pip install torch --index-url https://download.pytorch.org/whl/cu124`.

### 6. Config additions to `Settings`

| Variable | Default | Description |
|---|---|---|
| `IMAGE_EDIT_MODEL_BACKEND` | `stub` | `stub` or `sana` |
| `IMAGE_EDIT_SANA_MODEL_ID` | `Efficient-Large-Model/Sana_1600M_1024px_diffusers` | HuggingFace model id |
| `IMAGE_EDIT_SANA_DEVICE` | `cpu` | `cpu`, `cuda`, `mps` |
| `IMAGE_EDIT_SANA_TORCH_DTYPE` | `float32` | `float32`, `float16`, `bfloat16` |
| `IMAGE_EDIT_SANA_NUM_INFERENCE_STEPS` | `20` | Denoising steps |
| `IMAGE_EDIT_SANA_OUTPUT_WIDTH` | `1024` | Output image width |
| `IMAGE_EDIT_SANA_OUTPUT_HEIGHT` | `1024` | Output image height |

Recommended for GPU: `SANA_DEVICE=cuda`, `SANA_TORCH_DTYPE=float16`. For Apple Silicon: `SANA_DEVICE=mps`, `SANA_TORCH_DTYPE=float16`.

### 7. `SanaPipeline` module layout

```
services/pipelines/
  stub.py       (existing)
  sana.py       (new)
```

`sana.py` exposes one class — `SanaPipeline(settings: Settings)`. The constructor calls `diffusers.SanaPipeline.from_pretrained(...)` with the configured dtype and device. `run(faces, prompt, output_path)` calls the diffusers pipeline via `asyncio.to_thread`, saves the first image as PNG, and returns `output_path`. `faces` is accepted but unused in this change.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Sana 1.6B in fp32 needs ~12 GB RAM | Document: use `SANA_TORCH_DTYPE=float16` on GPU to halve memory |
| First `run` triggers HuggingFace model download (~6 GB) | Document pre-download step in README: `python -c "from diffusers import SanaPipeline; SanaPipeline.from_pretrained(...)"` |
| CUDA torch wheel not auto-installed | Document CUDA install instructions in README; pyproject.toml ships CPU wheel |
| Tests that import `SanaPipeline` would fail without ML deps | Tests use `StubPipeline` only; no test should import `SanaPipeline` directly |

## Open Questions

- Which Sana variant to default to: `Sana_1600M_1024px_diffusers` (1.6B, better quality) or `Sana_600M_1024px_diffusers` (600M, faster, half the RAM)? Decision deferred: default to 1.6B, let the user override via `SANA_MODEL_ID`.
