# Proposal

## Why

The product's core value is generating a composed photo from one or more reference faces plus a text prompt (e.g., "a family hiking in the Alps at sunset"). Nothing in the project does this yet — the repo is a bare scaffold. Shipping any UI, any auth, any storage is premature until the generation capability has a defined contract. This change establishes that contract: the request/response shape, the processing model (async with job polling), and the acceptance criteria the server must meet. Everything else — the Flutter app, authentication, galleries, billing — will consume or depend on this capability.

## What Changes

- New HTTP endpoint `POST /generations` accepting 1–4 reference face images plus a text prompt, returning a `job_id` immediately (async).
- New HTTP endpoint `GET /generations/{job_id}` returning job status (`queued`, `running`, `succeeded`, `failed`) and, when succeeded, a URL to the generated image.
- New background job runner that executes a generation pipeline per job. The specific model pipeline (SDXL + identity-preserving adapter, FLUX + PhotoMaker, ComfyUI backend, etc.) is a design-level decision and not fixed by this spec.
- Reference face images are accepted as `multipart/form-data` uploads, validated for size and format, and held only for the lifetime of the job.
- Generated images are stored on local disk and served from a static route; retention policy is design-level, not spec-level.
- Auth is explicitly **out of scope**: the endpoints are unauthenticated in this change. A follow-up change must add auth before any public exposure. The spec records this as a deferred requirement so it cannot be forgotten.

## Capabilities

### New Capabilities
- `photo-generation`: The system's core capability — accepting reference faces and a prompt, running an identity-preserving generation pipeline asynchronously, and returning a composed image. Owns the request contract, the job lifecycle, input validation rules, and the deferred-auth constraint. Future requirements like batching, multiple output variants, style controls, and NSFW filtering belong here as the capability matures.

### Modified Capabilities
<!-- None — this is the first capability in the project. -->

## Impact

- **Code (new):** `server/src/image_edit_server/` gains an API router module, a job manager (in-memory for v1, interface shaped so a Redis/queue backend can slot in later), a pipeline executor interface, and a storage module for input/output image files.
- **Dependencies (new):** eventually `torch`, `diffusers`, `transformers`, `insightface`, and friends — intentionally **not** installed by this change, since the pipeline implementation is design-level. The spec is pipeline-agnostic.
- **Config (new):** environment variables for max concurrent jobs, output retention, and storage root. Defined concretely in `design.md`.
- **Filesystem:** generated images and transient face uploads land under a configurable storage root (default `./storage/`), gitignored.
- **Downstream (future):** the Flutter app in `app/` will consume this contract. The OpenAPI schema FastAPI auto-generates from these endpoints is the shared source of truth.
- **Not touched:** no auth, no user accounts, no billing, no gallery, no on-device inference. All deferred to later changes.
