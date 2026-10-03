# Tasks

## 1. Dependencies

- [x] 1.1 Add `[dependency-groups] ml = [...]` group to `server/pyproject.toml` with `torch`, `diffusers>=0.32`, `transformers>=4.45`, `accelerate>=0.30`, `sentencepiece>=0.2`, `protobuf>=5.0`; verify `uv lock` succeeds from `server/`

## 2. Config

- [x] 2.1 Add `MODEL_BACKEND: str = "stub"`, `SANA_MODEL_ID: str = "Efficient-Large-Model/Sana_1600M_1024px_diffusers"`, `SANA_DEVICE: str = "cpu"`, `SANA_TORCH_DTYPE: str = "float32"`, `SANA_NUM_INFERENCE_STEPS: int = 20`, `SANA_OUTPUT_WIDTH: int = 1024`, `SANA_OUTPUT_HEIGHT: int = 1024` to `Settings` in `configs/settings.py`; verify `Settings()` instantiates without error
- [x] 2.2 Add all 7 new env vars to the config table in `server/README.md`; verify the table renders correctly

## 3. SanaPipeline

- [x] 3.1 Create `server/src/image_edit_server/services/pipelines/sana.py` with `SanaPipeline` class; constructor accepts `Settings` and calls `diffusers.SanaPipeline.from_pretrained` with `SANA_MODEL_ID`, resolved torch dtype, and `device_map=SANA_DEVICE`; verify the file exists and the class can be imported when diffusers is present
- [x] 3.2 Implement `async run(faces, prompt, output_path)`: wrap the synchronous diffusers call with `asyncio.to_thread`; accept `faces` without using them (face conditioning deferred); save the first output image as PNG to `output_path`; verify the method signature satisfies the `GenerationPipeline` Protocol
- [x] 3.3 Write `server/tests/services/pipelines/test_sana.py` that patches `diffusers.SanaPipeline` (so the test runs without ML deps installed); verify constructor calls `from_pretrained` with the right args and `run` produces a PNG at the given path; verify `uv run pytest tests/services/pipelines/test_sana.py` passes

## 4. Pipeline Factory

- [x] 4.1 Replace `pipeline = StubPipeline()` in `main.py` with a `_make_pipeline(cfg: Settings)` function: return `StubPipeline()` when `cfg.MODEL_BACKEND == "stub"`, import and return `SanaPipeline(cfg)` when `cfg.MODEL_BACKEND == "sana"`, raise `ValueError` for unknown backends; import `SanaPipeline` inside the `sana` branch to avoid loading ML deps on the stub path
- [x] 4.2 Verify all existing tests still pass with `uv run pytest`; `MODEL_BACKEND` defaults to `stub` so no ML deps are needed

## 5. Documentation and Manual Smoke Test

- [x] 5.1 Add a `## Running with Sana` section to `server/README.md` with: `uv sync --group ml`, model pre-download command (`python -c "from diffusers import SanaPipeline; SanaPipeline.from_pretrained('Efficient-Large-Model/Sana_1600M_1024px_diffusers')"`), and example start command with `IMAGE_EDIT_MODEL_BACKEND=sana IMAGE_EDIT_SANA_DEVICE=cpu`; verify the commands are accurate
- [ ] 5.2 Start the server with `IMAGE_EDIT_MODEL_BACKEND=sana IMAGE_EDIT_SANA_DEVICE=cpu IMAGE_EDIT_SANA_TORCH_DTYPE=float32`, submit a job with a face image and prompt, poll until `succeeded`, download the PNG; verify the output is a real generated image (not a solid color)
