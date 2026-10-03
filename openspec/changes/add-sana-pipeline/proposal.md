# Proposal

## Why

The `StubPipeline` returns a solid-color placeholder, so the application cannot produce real output for testing or demonstration. This change wires in NVIDIA Sana — a fast, low-VRAM text-to-image model — so the generation pipeline runs real inference end-to-end on local hardware.

## What Changes

- Add `SanaPipeline` concrete implementation under `services/pipelines/sana.py`, satisfying the existing `GenerationPipeline` protocol.
- Add model configuration fields to `Settings`: `MODEL_BACKEND` (selects stub vs. sana), `SANA_MODEL_ID`, `SANA_DEVICE`, `SANA_TORCH_DTYPE`, `SANA_OUTPUT_WIDTH`, `SANA_OUTPUT_HEIGHT`, `SANA_NUM_INFERENCE_STEPS`.
- `main.py` factory selects the pipeline from config at startup, so the stub remains available for tests and CI without ML deps.
- Add runtime ML dependencies: `torch`, `diffusers>=0.32` (Sana support landed in 0.32), `transformers`, `accelerate`, `sentencepiece`, `protobuf`.
- Update `server/README.md` with model download and startup instructions.

**Out of scope for this change:** Face identity conditioning. Uploaded reference images are still accepted and validated per the existing API contract, but are not passed to the model. Face conditioning is deferred to a subsequent change.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `photo-generation`: Add requirement — the system SHALL generate the output image using a real inference model rather than a placeholder, and SHALL NOT return a solid-color stub image in production mode.

## Impact

- `server/pyproject.toml` — new ML deps group; heavy packages only installed on the GPU box, not required for CI (stub runs without them).
- `server/src/image_edit_server/configs/settings.py` — new model config fields.
- `server/src/image_edit_server/services/pipelines/sana.py` — new file.
- `server/src/image_edit_server/main.py` — pipeline factory logic.
- `server/README.md` — model download and run instructions updated.
