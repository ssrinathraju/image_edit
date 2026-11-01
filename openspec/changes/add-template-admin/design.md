# Design

## Context

- **Catalog today:** `load_catalog(TEMPLATES_DIR)` reads `catalog.json` and checks that each preview exists. It builds an immutable `TemplateCatalog`, sorted by popularity then title. `create_app` injects it through `get_catalog`, and previews are mounted from `TEMPLATES_DIR/previews`.
- **How generations use it:** `generation_service` resolves a template's prompt with `catalog.get(id)` at submit time, so an accepted job already holds its prompt.
- **Server process:** one process. The job store is in memory, so running several workers isn't supported.
- **Accounts:** `SqliteUserStore`, at schema version 7, composed from mixins (`user_store_*.py`). Column presence decides migrations, under one connection lock.
- **Operator tools:** `scripts/set_plan.py` and `scripts/reports.py` are the pattern for operator tooling, and have no public endpoints.
- **Safety:** `SafetyService.is_prompt_blocked` applies the blocked-term list.

## Goals and non-goals

**Goals:**
- an admin role granted outside HTTP;
- an admin API to list, create, edit, retire and restore templates;
- changes live without a restart;
- the same text screening as user prompts;
- normalised previews;
- an audit log.

**Non-goals:**
- admin UI (app or web);
- deleting templates or changing their id;
- popularity from usage;
- the NSFW classifier on previews;
- multi-process catalog sync.

## Decisions

### Decision 1: Templates live in `app.db`; the seed is imported once
Schema v8 adds a `templates` table:
- `id` (primary key), `title`, `tags_json`, `popularity`, `prompt`, `preview_file`, `retired` (0 or 1), `updated_at`;
- a `meta` row `templates_seeded`, which the import sets.

At startup, `create_app` calls `seed_templates_if_needed(store, seed_dir, previews_dir)`. If `templates_seeded` is unset, it validates the seed with the existing `load_catalog` rules, copies each preview into `<STORAGE_ROOT>/template-previews/` under a content-hashed name (Decision 4), inserts the rows, and sets the marker, all in one transaction. A bad seed fails startup and names the entry, as today. Once seeded, the seed folder is never read again, so retiring every template does not bring the seed back.

After that, startup builds the catalog from the stored rows and fails if a stored preview file is missing. This keeps the "Validate the catalog at startup" guarantee.

**Rejected:** rewriting `catalog.json` in place. The server would write into a folder checked into git, and there would be no transaction around the file and its previews. The user chose SQLite.

**Rejected:** a separate `templates.db`. The templates need no separate lifecycle, and one database keeps backups and migration in one place.

### Decision 2: One in-memory catalog holder, swapped after each commit
`CatalogHolder` holds the current immutable `TemplateCatalog`, built from non-retired rows:
- `get_catalog` returns `holder.current`;
- after an admin write commits, the service rebuilds the catalog from the store and replaces `holder.current` in one reference assignment;
- readers always see either the old or the new catalog, never a mix.

Writes are serialised by an `asyncio.Lock` in the service, and the store's own lock guards the SQLite connection.

This meets the user's "live within 30 seconds" choice: the change is visible on the next request. No 30-second poll is needed, because the only writer is this process.

**Rejected:** polling the database every 30 s. It only matters with several processes, and the server can't run as several processes anyway, because of the in-memory job store. Add polling when that changes.

`GET /admin/templates` reads the store directly, because it includes retired rows.

### Decision 3: Admin role is a column; `set_role.py` is the only way to set it
Schema v8 adds `users.role TEXT NOT NULL DEFAULT 'user'`, so every existing account gets `user`. `User` gains `role`. `api/deps.py` adds `require_admin`: it loads the current user from the session, as `get_current_user` does, and raises 403 `admin_required` unless `role == 'admin'`. It reads the role on every request, so removing it takes effect at once.

`scripts/set_role.py --email --role admin|user` follows `set_plan.py`:
- it normalises the email;
- it refuses a missing database or an unknown email with a non-zero exit;
- it prints the outcome without the email.

**Rejected:** an `ADMIN_EMAILS` setting. After an email change, admin rights would follow the new address, and the user chose the script.

**Rejected:** re-authentication on each write. The user chose the session alone, with audit logging (Decision 7).

### Decision 4: Previews are normalised to 512×512 WebP with a content-hashed name
The service reads the upload with a 2 MB cap: it reads 2 MB plus 1 byte and refuses anything longer. It then:
1. opens it with Pillow, accepting only PNG, JPEG and WebP by the decoded format, not by the file name or the Content-Type;
2. calls `verify()`, then reopens and `load()`s it;
3. converts it to RGB, centre-crops it to a square and resizes it to 512 with LANCZOS;
4. encodes it as WebP at quality 80, the same as `generate_template_previews.py`.

The file is named `<id>-<first 12 hex of sha256 of the WebP bytes>.webp`, so a replaced preview gets a new `preview_url`.

Pillow's decompression-bomb guard stays on, and an image over the guard is refused as `invalid_preview`. Decoding runs in `asyncio.to_thread`.

**Rejected:** keeping the upload as is. It would allow arbitrary sizes and formats, and the old URL would stay cached after a replace.

**Rejected:** a cache-busting query string. A content-hashed name is simpler to serve with `StaticFiles`.

### Decision 5: The write order keeps files and rows consistent
For a create, or an edit with a preview:
1. write the new preview to a temporary name, then rename it to its final name;
2. commit the row;
3. swap the catalog;
4. delete the old preview file, if it was replaced. A failed delete is logged, and the orphan is removed at the next startup.

If the commit fails, the new file is deleted and the request fails with 500, leaving no row change. Startup removes any file in `template-previews/` that no row references. That covers a crash between steps 1 and 2.

### Decision 6: Validation and screening happen before any write
The service validates all supplied fields first (the limits in the spec), then screens the title, each tag and the prompt with `SafetyService.is_prompt_blocked`, then decodes the preview. The first failure answers 400 with `invalid_template_field`, `template_text_blocked` or `invalid_preview`, and the body's `field` names the field. Nothing is written before every check passes.

How fields are cleaned up:
- tags are trimmed, lower-cased and de-duplicated in order;
- the title and prompt are trimmed.

The existing pydantic `Template` model keeps the id pattern and the 500-character prompt limit. It gains the title (60), tag (10 × 30) and popularity limits.

### Decision 7: Audit log lines carry ids only
On success the service logs `template_admin action=<create|edit|retire|restore> template=<id> admin=<user_id>` at INFO. An edit also logs which fields changed, by name, with no values. Refusals log `template_admin_refused action=<…> template=<id> admin=<user_id> reason=<code>`.

**Rejected:** an audit table. Logs already carry the safety and auth events, and nothing reads an audit history yet.

### Decision 8: Endpoints and error shapes
- **Router:** `api/admin_templates.py`, with the prefix `/admin/templates`, using `require_admin`.
- **Request format:** multipart for create and edit, because of the image. Tags are one comma-separated string. `popularity` is parsed as an integer, and a non-integer value is `invalid_template_field`.
- **Errors** use the existing `ErrorBody {error, detail}`, plus an optional `field`.
- **Retire and restore** are idempotent.
- **The public `GET /templates`** and the preview mount are unchanged in shape. The mount moves to `<STORAGE_ROOT>/template-previews`, and `PREVIEW_URL_PREFIX` stays `/template-previews`.

## API summary

| Method and path | Success | Errors |
|---|---|---|
| `GET /admin/templates` | 200, list (Decision 2) | 401, 403 `admin_required` |
| `POST /admin/templates` | 201, template | 400 `invalid_template_field` / `template_text_blocked` / `invalid_preview`; 409 `template_exists`; 401; 403 |
| `PATCH /admin/templates/{id}` | 200, template | 400 (as above, plus no fields given); 404 `template_not_found`; 401; 403 |
| `POST /admin/templates/{id}/retire` and `/restore` | 200, template | 404 `template_not_found`; 401; 403 |

## Risks and trade-offs

- **Data stored:**
  - template rows (title, tags, popularity, prompt, preview file name, retired flag, `updated_at`) and preview images, kept until an operator removes them;
  - the account `role` column.

  None of it is personal data. Previews are generated or stock images, not user faces.
- **Who can read it:**
  - public: title, tags and preview through `GET /templates`, as today;
  - admins: prompts and retired templates, through `GET /admin/templates`;
  - nobody else can read prompts, so the "Keep template prompts server-side" requirement still holds for the public endpoint.
- **Logging:** Decision 7, with ids only and no prompt, title, tags or email. `set_role.py` prints no email.
- **Migration (v7 → v8):** it adds `users.role` with the default `user`, the `templates` table and the `meta` table, using the existing column-presence approach, so a half-migrated file heals. The first start after upgrade imports the seed. Template ids are unchanged, so existing jobs, creations and Make another keep working. Preview URLs change to hashed names. The app reads `preview_url` from each listing, so cached old URLs just miss once.
- **Failure and retry:**
  - Every refusal changes nothing (Decision 6).
  - A database error answers 500 and cleans up the new file (Decision 5).
  - A client may retry a create: a second create returns 409 `template_exists`, and the admin can then check with `GET /admin/templates`.
- **Background tasks:** none new. The startup orphan sweep runs once and logs and continues on a failed delete.
- **Thread-safety:**
  - admin writes are serialised by an `asyncio.Lock`;
  - SQLite access is under the store's lock;
  - the catalog swap is a single reference assignment to an immutable object;
  - generations read whichever catalog is current at submit time and copy the prompt into the job.
- **Security:**
  - The admin role is granted only from the server host.
  - A leaked admin token can change templates until the session expires or the role is removed, but it cannot read user data through these endpoints.
  - Uploads are decoded with Pillow's bomb guard, capped at 2 MB and re-encoded, so no uploaded bytes are served as is.
- **Trade-off:** the public listing order and the search behaviour are unchanged. Popularity is still set by hand.
