# Design

## Context

See `proposal.md` for motivation. The server package is a fresh `uv init` with FastAPI, Uvicorn, Pillow, and `python-multipart` installed; no routes, no business logic, no model code exists yet. The deployment target is a single self-hosted GPU box the operator controls. The spec (`specs/photo-generation/spec.md`) defines the external contract; this document is only about how to realize it.

Constraints that shape the approach:
- The real generation pipeline (SDXL + InstantID, FLUX + PhotoMaker, ComfyUI, etc.) is undecided and heavy (multi-GB weights, long-running). We do not want this change to pin a model choice.
- Clients will mostly be a Flutter mobile app over the public internet eventually, which rules out long-held synchronous HTTP connections.
- Single-box, single-GPU v1 — no need for Redis or a message broker yet, but we want to avoid locking out that future.

## Goals / Non-Goals

**Goals:**
- Realize the nine spec requirements with a FastAPI app that can be run via `uv run uvicorn image_edit_server.main:app`.
- Make the generation pipeline a seam (interface) so the real model can be plugged in without touching the API or job layer.
- Keep the apply-phase diff small enough to review in one sitting: stubbed pipeline, in-memory job store, no distributed systems.
- Have FastAPI auto-produce an OpenAPI schema that the Flutter client can code-gen against later.

**Non-Goals:**
- Choosing or integrating a real generation model. The apply phase ships a stub pipeline that returns a solid-color PNG so the full request → job → image flow is exercisable end-to-end without any ML stack installed.
- Authentication, rate limiting, multi-user isolation, or billing — explicitly deferred per the proposal.
- Persistent job store, horizontal scaling, retry logic for transient model failures — these are future concerns.
- A client SDK or the Flutter app wiring.

## Decisions

### Module layout (layered)

Per `CLAUDE.md` rule 1, `server/src/image_edit_server/` is laid out by responsibility:

```
server/src/image_edit_server/
├── configs/                       # settings + env parsing
│   └── settings.py
├── schemas/                       # Pydantic + domain DTOs (NOT ML models)
│   ├── job.py                     # Job dataclass + JobStatus enum
│   └── api.py                     # JobSubmission, JobStatusResponse, ErrorBody
├── core/                          # pure domain, no I/O
│   ├── job_store.py               # JobStore Protocol
│   └── pipeline.py                # GenerationPipeline Protocol
├── repos/                         # data-access impls
│   ├── file_storage.py            # inputs/outputs on local disk
│   └── in_memory_job_store.py     # JobStore impl backed by a dict + lock
├── services/                      # orchestration (API-free business logic)
│   ├── generation_service.py      # submit, status lookup, result url resolution
│   ├── worker.py                  # background job runner
│   └── pipelines/
│       └── stub.py                # StubPipeline — placeholder PNG
├── api/                           # FastAPI routers only; thin
│   └── generations.py
└── main.py                        # app factory, lifespan, static mount
```

Rationale: strict layering keeps HTTP concerns out of pipelines, pipelines out of storage, and all three testable in isolation. `services/` is the only layer allowed to orchestrate across `repos/` and `core/`. The `api/` layer stays thin — parse, delegate, serialize.

### API shape

Two routes, both under `/generations`:

```
POST /generations
  Content-Type: multipart/form-data
  faces:  file[]   # 1..4 image files
  prompt: string   # 1..MAX_PROMPT_CHARS

  → 202 Accepted
    { "job_id": "01HE..." }

GET /generations/{job_id}
  → 200 OK
    { "job_id": "...", "status": "queued" | "running" | "succeeded" | "failed",
      "result_url": "/images/<job_id>.png"?,   # present iff succeeded
      "error": "pipeline_failed" | ... ?        # present iff failed
    }
  → 404 Not Found
```

Generated images are served via a `StaticFiles` mount at `/images/`, backed by `<STORAGE_ROOT>/outputs/`. `result_url` is a relative path so it works behind reverse proxies.

Job ids are ULIDs (sortable, URL-safe) rather than UUID4s — no library pin here; the apply phase can pick `python-ulid` or roll one.

**Alternatives considered.** A single `POST /generate` that blocks and streams the image back (rejected: mobile networks + 5–60s pipelines = timeout bait). WebSockets for job status (rejected: polling is simpler, scales fine for v1, and matches how most image-gen APIs work publicly).

### Async execution: in-memory job store + asyncio worker

A `JobStore` Protocol (in `core/job_store.py`) defines `create(job) -> id`, `get(id) -> Job | None`, `update(id, patch)`, and `list_queued() -> Iterable[Job]`. The v1 implementation `InMemoryJobStore` lives in `repos/in_memory_job_store.py` and is a dict guarded by an asyncio lock. On FastAPI startup, a background worker task (`asyncio.create_task`) loops: pull the next queued job, mark it `running`, invoke the pipeline, write the output, mark `succeeded` or `failed`, delete reference uploads.

Concurrency defaults to 1 (one job at a time). Configurable via `JOB_CONCURRENCY` — the worker spawns N parallel coroutines, each pulling from the same store. Real pipelines are usually GPU-bound and 1 is the right default.

**Alternatives considered.** Celery + Redis (rejected: too heavy for v1, premature). `arq` or `rq` (rejected: same, and adds a Redis dependency). Threads instead of asyncio (rejected: FastAPI is already async; blocking work moves to `asyncio.to_thread` when the real pipeline arrives). The interface keeps all of these on the table.

### Pipeline abstraction

```python
# core/pipeline.py
class GenerationPipeline(Protocol):
    async def run(self, faces: list[Path], prompt: str) -> Path:
        """Return the path to the generated image on disk."""
```

The apply phase ships `StubPipeline` in `services/pipelines/stub.py`, which writes a 1024×1024 PNG filled with a deterministic color derived from the prompt (so tests can assert the file exists and is a valid image). The real pipeline will be a separate change that adds `torch`, `diffusers`, `insightface`, model weights, and a concrete implementation of this Protocol under `services/pipelines/`.

**Why a Protocol, not an ABC.** We want structural typing so a `ComfyUIPipeline` that calls a local ComfyUI server (no model code in this project) can also satisfy the contract without inheriting from anything.

### Storage layout

```
<STORAGE_ROOT>/
  inputs/<job_id>/face_0.jpg, face_1.jpg, ...   # deleted on terminal state
  outputs/<job_id>.png                          # served via /images/
```

Default `STORAGE_ROOT` is `./storage`. Added to `.gitignore` (the top-level `.gitignore` already excludes `outputs/` and `cache/`; we'll add `server/storage/`).

Retention of outputs is **not** enforced in this change — a `OUTPUT_RETENTION_HOURS` setting is defined and read, but the sweep task is a one-line TODO stub. Enforcement is explicitly a future change; a note in `tasks.md` records the gap.

### Config

`pydantic-settings` with a `Settings` singleton in `configs/settings.py`:

| Setting | Default | Spec linkage |
|---|---|---|
| `STORAGE_ROOT` | `./storage` | — |
| `MAX_UPLOAD_BYTES` | `10 * 1024 * 1024` | "Reject invalid reference images" |
| `MAX_FACES` | `4` | "Reject requests with an invalid face count" |
| `MIN_FACES` | `1` | "Reject requests with an invalid face count" |
| `MAX_PROMPT_CHARS` | `500` | "Reject invalid prompts" |
| `JOB_CONCURRENCY` | `1` | — |
| `OUTPUT_RETENTION_HOURS` | `24` | — (deferred enforcement) |
| `ACCEPTED_IMAGE_TYPES` | `image/jpeg,image/png,image/webp` | "Reject invalid reference images" |

All overridable via environment variables (`IMAGE_EDIT_MAX_FACES=...`).

### Validation strategy

Pydantic models handle shape; a small validator function enforces the file-level checks (count, MIME, size) before any disk writes. Rejected requests must not leave files on disk — the handler reads uploads into memory bounded by `MAX_UPLOAD_BYTES` before accepting.

### Error model

Standard FastAPI `HTTPException` with a shared error schema in OpenAPI:

```json
{ "error": "invalid_face_count", "detail": "faces must be between 1 and 4" }
```

Error codes are short machine strings (`invalid_face_count`, `invalid_image`, `invalid_prompt`, `pipeline_failed`, `not_found`). Human text goes in `detail`.

## Risks / Trade-offs

- **In-memory job store loses state on restart** → acceptable for local dev; the `JobStore` interface lets a Redis/SQLite impl drop in later without touching the API layer.
- **Static-file serving via FastAPI is fine locally, inadequate publicly** (no signed URLs, no CDN) → noted here; a future change can add a `StorageBackend` interface analogous to `JobStore` with an S3-backed impl.
- **No pipeline means no end-to-end "real" test** → mitigated by stubbing with a pipeline that still writes a valid PNG, so the full request/job/download path is exercisable in CI.
- **No auth** → recorded as a spec-level requirement so it cannot be silently forgotten; `tasks.md` ends with a reminder that the next change should be `add-authentication`.
- **Multipart face uploads are read into memory** → with `MAX_UPLOAD_BYTES=10MB` and up to 4 faces, peak per-request RAM is ~40 MB. Fine for v1; revisit if we raise the cap.

## Migration Plan

Nothing to migrate — this is the first capability. The apply phase introduces new files only.

## Open Questions

None that block implementation. The model-pipeline choice is a known deferred decision and does not block this change: the Protocol seam absorbs it.
