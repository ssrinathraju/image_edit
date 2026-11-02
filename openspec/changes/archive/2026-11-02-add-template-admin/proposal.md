# Proposal

## Why

The catalog is 12 entries in `server/seed/templates/catalog.json`, loaded once at startup. Adding, fixing or pulling a template means editing a file in the repo, regenerating previews, and redeploying or restarting. Templates are the main way users get good results, and a template with a content problem needs to come down quickly. So templates need managing on a running server.

## What Changes

- **Admin role:** a `role` on accounts (`user` or `admin`), granted and removed only by the new operator script `scripts/set_role.py`. No endpoint can grant it.
- **Admin API (curl only):**
  - `GET /admin/templates` lists all templates, with prompts and retired ones;
  - `POST /admin/templates` creates one (multipart, with a preview image);
  - `PATCH /admin/templates/{id}` edits one;
  - `POST /admin/templates/{id}/retire` and `/restore`.

  Non-admins get 403 `admin_required`. No re-authentication is needed beyond the session.
- **Stored templates:** a `templates` table in `app.db` (schema v8). Previews go in `<storage root>/template-previews/`. The seed catalog is imported once, on the first start with a database that was never seeded. After that it is ignored.
- **Live changes:** each change applies from the next request, without a restart.
- **Retire:** hidden from `GET /templates` and search, and new generations get `invalid_template`. Jobs already accepted finish. Restore brings it back, because nothing is deleted.
- **Checks on create and edit:**
  - field limits;
  - title, tags and prompt screened with the blocked-term list;
  - a PNG, JPEG or WebP preview of at most 2 MB, stored as a 512×512 WebP.

  A new preview gets a new URL.
- **Audit:** one log line per change, with the action, template id and admin account id, and no text.
- **README:** curl examples and the `set_role.py` usage.

Out of scope:
- admin screens in the app, and a web admin UI;
- deleting templates;
- popularity computed from real usage;
- running the NSFW classifier on previews;
- editing a template's id;
- per-template analytics.

## Capabilities

### New Capabilities
- `template-admin`: the admin role and its tooling, plus the admin endpoints, validation, screening, preview handling and audit logging.

### Modified Capabilities
- `template-catalog`: the catalog source is now the stored templates after a one-time seed import. Replacing a preview changes its URL. Retired templates are hidden.
- `photo-generation`: a retired template is rejected as `invalid_template`, and accepted jobs keep their prompt.

## Impact

- **Server only.**
  - New: `repos/user_store_templates.py`, `services/template_admin_service.py`, `api/admin_templates.py`, `scripts/set_role.py`.
  - Changed: `repos/template_catalog.py` (built from stored rows), `repos/user_store.py` (schema v8: the `role` column, the `templates` table and a seeded marker), `api/deps.py` (an admin dependency), and `main.py` (the seed import, the shared catalog holder, and the preview mount from the storage root).
  - `server/README.md`.
- **App:** unchanged. It already reads `GET /templates`, and a retired template already shows "Could not load this template.".
- **Dependencies:** none new. Pillow is already used for previews.
- **Existing data:** `app.db` upgrades from v7 to v8. Every existing account starts as `user`. The 12 seed templates are imported with their ids unchanged, so existing creations' Make another keeps working.
