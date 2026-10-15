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

## Accounts and authentication

Generation endpoints require a session. Register (or log in) to get a bearer token, then send it as
`Authorization: Bearer <token>`. `GET /templates` and the template previews stay public.

```bash
# Register → 201 {"token": "...", "id": "...", "email": "ana@example.com"}
# `referral_code` is optional; an unknown code is a 400 invalid_referral_code
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "correct horse battery"}'

# Log in → 200 with a new token; the same error for a wrong password and an unknown email
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "correct horse battery"}'

TOKEN=<token from the response>

curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# → {"id": "...", "email": "ana@example.com", "created_at": "...", "plan": "free",
#    "usage": {"daily_limit": 3, "used_today": 0, "bonus_credits": 0, "remaining": 3,
#              "resets_at": "2026-10-17T00:00:00+00:00", "plan_limits": {"free": 3, "premium": 30}},
#    "referral": {"code": "K7M2QX9P", "rewards": 0, "max_rewards": 10, "bonus_per_referral": 5}}

# Log out: revokes this token only → 204
curl -X POST http://localhost:8000/auth/logout -H "Authorization: Bearer $TOKEN"

# Delete the account, its sessions, jobs and generated images → 204 (403 on a wrong password)
curl -X DELETE http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"password": "correct horse battery"}'
```

Errors: `401 unauthorized` (missing, unknown, expired or revoked token), `409 email_taken`,
`400 invalid_credentials_format` (malformed email or a password outside 8-128 characters),
`401 invalid_credentials`, `429 too_many_attempts` (5 failed logins for one email locks it for
15 minutes; wrong passwords on account deletion count toward the same limit),
`403 invalid_password` (account deletion), `422` (email over 254 or password over 128 characters).

Notes:

- Users and sessions live in a SQLite file, `app.db` inside `IMAGE_EDIT_STORAGE_ROOT`
  (override with `IMAGE_EDIT_AUTH_DB_PATH`). Jobs are still in memory and are lost on restart.
- Passwords travel as plain JSON, so outside local development the API **must** be served over
  HTTPS.
- Generated images at `/images/<job_id>.png` are not authenticated; job ids are unguessable and
  only the owner can look them up, but treat the URLs as secrets.

## Plans, daily limit, and referrals

Every account is on the `free` plan (3 generations per UTC day) or `premium` (30). A generation
is reserved when `POST /generations` is accepted and returned if the job ends `failed`; requests
that fail validation never use one. When the daily allowance and any bonus credits are gone the
server answers:

```
429 {"detail": {"error": "quota_exceeded", "detail": "the daily generation limit has been reached"}}
```

Bonus credits are one-time and are spent only after the daily allowance. Each account has a
referral code (`referral.code` in `/me`). Registering with someone's code gives both accounts
`REFERRAL_BONUS` credits; a referrer is rewarded for at most `REFERRAL_MAX_REWARDS` friends.

```bash
# Register with a friend's code (case and surrounding spaces are ignored)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ben@example.com", "password": "correct horse battery", "referral_code": "k7m2qx9p"}'
```

There is no endpoint that changes a plan. Promote or demote an account from `server/` with the
operator script, which reads the same `IMAGE_EDIT_*` settings as the server (so run it with the
same `IMAGE_EDIT_STORAGE_ROOT` or `IMAGE_EDIT_AUTH_DB_PATH`). A running server picks the change up
on the next request:

```bash
uv run python scripts/set_plan.py --email ana@example.com --plan premium
```

`set_plan.py` prints the database it changed and refuses to run when that file does not exist, so
a run from the wrong directory fails loudly instead of creating an empty database.

Jobs are held in memory, so a restart loses any job that was queued or running. Their generations
are refunded automatically when the server starts again. This assumes a single server process: a
second instance on the same `app.db` would refund the first one's in-flight jobs.

The first start after upgrading migrates an existing `app.db` in place: users keep their data,
become `free` with no bonus credits, and receive referral codes. The migration is idempotent.

## Submit a generation job

```bash
curl -X POST http://localhost:8000/generations \
  -H "Authorization: Bearer $TOKEN" \
  -F "prompt=a family hiking in the Alps at sunset" \
  -F "faces=@/path/to/face1.jpg" \
  -F "faces=@/path/to/face2.jpg"
# → {"job_id": "01HE..."}
```

## Submit from a template

Browse the catalog (add `?q=` to search titles and tags), then submit with a `template_id`
instead of a `prompt` (send exactly one of the two):

```bash
curl "http://localhost:8000/templates?q=beach"
# → [{"id": "golden-hour-beach", "title": "Golden Hour Beach", "tags": [...],
#     "preview_url": "/template-previews/golden-hour-beach.webp"}]

curl -X POST http://localhost:8000/generations \
  -H "Authorization: Bearer $TOKEN" \
  -F "template_id=golden-hour-beach" \
  -F "faces=@/path/to/face.jpg"
# → {"job_id": "01HE..."}
```

Template prompts stay on the server. Sending both `prompt` and `template_id`, or an unknown
`template_id`, returns 400 with error code `invalid_template`.

## Poll for status

```bash
curl http://localhost:8000/generations/<job_id> -H "Authorization: Bearer $TOKEN"
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
| `IMAGE_EDIT_TEMPLATES_DIR` | `./seed/templates` | Folder holding `catalog.json` and `previews/` |
| `IMAGE_EDIT_AUTH_DB_PATH` | _(empty)_ | SQLite file for users and sessions; empty means `<STORAGE_ROOT>/app.db` |
| `IMAGE_EDIT_SESSION_TTL_DAYS` | `30` | Session lifetime, fixed from login |
| `IMAGE_EDIT_PASSWORD_MIN_CHARS` | `8` | Minimum password length |
| `IMAGE_EDIT_PASSWORD_MAX_CHARS` | `128` | Maximum password length |
| `IMAGE_EDIT_LOGIN_MAX_FAILURES` | `5` | Consecutive failed logins per email before lockout |
| `IMAGE_EDIT_LOGIN_LOCKOUT_MINUTES` | `15` | Lockout length, counted from the latest failure |
| `IMAGE_EDIT_FREE_DAILY_LIMIT` | `3` | Generations per UTC day on the `free` plan |
| `IMAGE_EDIT_PREMIUM_DAILY_LIMIT` | `30` | Generations per UTC day on the `premium` plan |
| `IMAGE_EDIT_REFERRAL_BONUS` | `5` | Bonus credits given to each side of a referral |
| `IMAGE_EDIT_REFERRAL_MAX_REWARDS` | `10` | Friends a single account is rewarded for |

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

## Template previews

Home-screen previews live in `seed/templates/previews/` (512x512 WebP). Regenerate them from `server/`:

```bash
# Pillow only: solid-color placeholders for any template missing a preview
uv run python scripts/generate_template_previews.py --placeholder

# Real previews through Sana (needs the ml group; ~3-5 min per image on CPU)
IMAGE_EDIT_SANA_NUM_INFERENCE_STEPS=4 \
  uv run --group ml python scripts/generate_template_previews.py

# Options: --force (overwrite existing), --only <template-id>, --templates-dir <path>
```
