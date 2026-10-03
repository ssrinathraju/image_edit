# Tasks

## 1. Setup

- [x] 1.1 Add runtime dependencies via `uv add pydantic-settings python-ulid` and dev dependencies via `uv add --dev pytest pytest-asyncio httpx`, then verify `uv sync` completes cleanly and `uv run python -c "import pydantic_settings, ulid, pytest, httpx"` exits 0.
- [x] 1.2 Create the layered module skeleton under `server/src/image_edit_server/` matching `design.md` ("Module layout"): `configs/`, `schemas/`, `core/`, `repos/`, `services/pipelines/`, `api/`, each with an `__init__.py`, plus a top-level `main.py`. Verify `uv run python -c "import image_edit_server; from image_edit_server import configs, schemas, core, repos, services, api"` succeeds.
- [x] 1.3 Extend `.gitignore` to exclude `server/storage/` and verify `git check-ignore server/storage/outputs/x.png` returns the path.

## 2. Configuration

- [x] 2.1 Implement `Settings` in `configs/settings.py` using `pydantic-settings` with the fields defined in `design.md` ("Config" table) and `env_prefix="IMAGE_EDIT_"`; verify `uv run python -c "from image_edit_server.configs.settings import Settings; print(Settings().MAX_FACES)"` prints `4`.
- [x] 2.2 Add `server/tests/configs/test_settings.py` asserting defaults match the design table and that `IMAGE_EDIT_MAX_FACES=2` env override is respected; verify `uv run pytest tests/configs/test_settings.py` passes.

## 3. Storage layer

- [x] 3.1 Implement `repos/file_storage.py` with `input_dir(job_id)`, `output_path(job_id)`, `save_upload(job_id, index, upload) -> Path`, `delete_inputs(job_id)`, driven by `Settings.STORAGE_ROOT`; verify by writing a byte string via `save_upload` in a temp dir and reading it back equal.
- [x] 3.2 Add `server/tests/repos/test_file_storage.py` covering `save_upload` + `delete_inputs` round trip and that `delete_inputs` removes the per-job directory; verify `uv run pytest tests/repos/test_file_storage.py` passes.

## 4. Domain schemas (Job)

- [x] 4.1 Define `Job` dataclass and `JobStatus` enum (`queued | running | succeeded | failed`) in `schemas/job.py`; verify `uv run python -c "from image_edit_server.schemas.job import Job, JobStatus"` succeeds and that `JobStatus.queued.value == 'queued'`.
- [x] 4.2 Add `server/tests/schemas/test_job.py` asserting enum values match the spec's status strings exactly (`queued`, `running`, `succeeded`, `failed`); verify `uv run pytest tests/schemas/test_job.py` passes.

## 5. Job store (interface + in-memory impl)

- [x] 5.1 Declare `JobStore` Protocol in `core/job_store.py` with `create`, `get`, `update`, `list_queued`; verify `uv run python -c "from image_edit_server.core.job_store import JobStore"` succeeds.
- [x] 5.2 Implement `InMemoryJobStore` in `repos/in_memory_job_store.py` guarded by an `asyncio.Lock`, assigning a ULID on `create`; verify by instantiating in an async test and round-tripping create → get.
- [x] 5.3 Add `server/tests/repos/test_in_memory_job_store.py` asserting ULID on create, patch-only update, `None` on unknown id, and that `list_queued` returns only `queued` jobs; verify `uv run pytest tests/repos/test_in_memory_job_store.py` passes.

## 6. Pipeline interface and stub

- [x] 6.1 Declare `GenerationPipeline` Protocol in `core/pipeline.py`; verify `uv run python -c "from image_edit_server.core.pipeline import GenerationPipeline"` succeeds.
- [x] 6.2 Implement `StubPipeline.run(faces, prompt)` in `services/pipelines/stub.py` writing a 1024×1024 PNG with a deterministic color derived from `prompt`; verify the output file opens with `PIL.Image.open` and reports `size == (1024, 1024)`.
- [x] 6.3 Add `server/tests/services/pipelines/test_stub.py` asserting the stub returns an existing readable PNG for a sample prompt; verify `uv run pytest tests/services/pipelines/test_stub.py` passes.

## 7. API schemas and submission

- [x] 7.1 Define Pydantic request/response models (`JobSubmission`, `JobStatusResponse`, `ErrorBody`) in `schemas/api.py`; verify `uv run python -c "from image_edit_server.schemas.api import JobSubmission; JobSubmission(job_id='x')"` succeeds.
- [x] 7.2 Implement `services/generation_service.py` exposing `submit(faces, prompt, store, storage) -> job_id` that handles validation (count, MIME, size, prompt bounds), persists uploads via `file_storage.save_upload`, creates a `queued` job via the store, and raises typed validation errors on invalid input; verify by unit-testing happy path and each rejection branch directly against the service (no HTTP layer).
- [x] 7.3 Implement `POST /generations` in `api/generations.py` as a thin FastAPI route that delegates to `generation_service.submit` and translates its validation errors to `HTTPException(400, ErrorBody(...))` per the spec; verify by hitting the route via FastAPI `TestClient` and asserting 202 + `job_id`.
- [x] 7.4 Add `server/tests/api/test_generations_submit.py` covering: happy path (202), 0 faces (400), 5 faces (400), non-image MIME (400), oversized upload (400), empty prompt (400), overlong prompt (400); verify `uv run pytest tests/api/test_generations_submit.py` passes.

## 8. API — status lookup and image delivery

- [x] 8.1 Add `generation_service.get_status(job_id, store) -> JobStatusResponse` that resolves the job, computes `result_url` for succeeded jobs, and returns `None` for unknown ids; verify by unit test against the service.
- [x] 8.2 Implement `GET /generations/{job_id}` in `api/generations.py` as a thin route delegating to `generation_service.get_status`; return 404 when the service returns `None`. Verify with a `TestClient` test for each of the four lifecycle states plus 404.
- [x] 8.3 In `main.py` mount `StaticFiles` at `/images/` serving `<STORAGE_ROOT>/outputs/`; verify by placing a PNG at `<STORAGE_ROOT>/outputs/foo.png` and asserting `GET /images/foo.png` returns 200 with `Content-Type: image/png`.
- [x] 8.4 Add `server/tests/api/test_generations_status.py` covering the four lifecycle states, 404 on unknown id, and that `result_url` on a succeeded job returns the image bytes; verify `uv run pytest tests/api/test_generations_status.py` passes.

## 9. Background worker

- [x] 9.1 Implement `services/worker.py` with an async loop that pulls `queued` jobs from the store, marks them `running`, invokes the configured `GenerationPipeline` (default `StubPipeline`), writes the output, marks `succeeded`, and on exception marks `failed` with a short `error` code. After any terminal state, call `file_storage.delete_inputs(job_id)`. Verify by driving one job through the loop in a test and asserting final `succeeded` status plus that the inputs dir is gone.
- [x] 9.2 Wire the worker to FastAPI startup in `main.py` via a `lifespan` context manager with `JOB_CONCURRENCY` parallel coroutines; verify by starting the app in-process with `TestClient`, submitting a job, polling until `succeeded`, and asserting `result_url` resolves to a valid PNG. This test exercises items 7.x, 8.x and 9.1 together — it is the first end-to-end check for this change.
- [x] 9.3 Add `server/tests/services/test_worker.py` for the single-job success path and a stub pipeline that raises, asserting the job transitions to `failed` with an `error` field and that inputs are still purged; verify `uv run pytest tests/services/test_worker.py` passes.

## 10. App wiring and docs

- [x] 10.1 In `main.py` build the FastAPI `app` factory, register the generations router, mount `/images/`, set `title`/`version` so OpenAPI output is clean, and expose a `create_app()` function the tests use; verify `uv run uvicorn image_edit_server.main:app --port 8000` starts and `curl -s localhost:8000/openapi.json | jq '.paths | keys'` lists `/generations` and `/generations/{job_id}`.
- [x] 10.2 Update `server/README.md` with run instructions (`uv sync`, `uv run uvicorn ...`), example curl for submit + poll, and the config env vars; verify the documented curl commands succeed against a running server.

## 11. Validation and handoff

- [x] 11.1 Run `openspec validate generate-photo-from-faces --strict` and verify it reports no errors.
- [x] 11.2 Run `uv run pytest` from `server/` and verify every test group above passes together (no cross-group regressions).
- [x] 11.3 Record the follow-up: the next OpenSpec change should be `add-authentication` (the spec marks the current unauthenticated behavior transitional). Verify by opening a tracking issue or dropping a one-line note in `openspec/changes/generate-photo-from-faces/proposal.md`'s Impact section — whichever the operator prefers.
