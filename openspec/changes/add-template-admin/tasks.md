# Tasks

Work on branch `feat/add-template-admin`. Do not push to `main`. All work is in `server/`; the app is not changed. "Decision N" refers to `design.md`. Tests use temporary storage roots and a temporary copy of the seed folder, and never touch `server/storage/` or `server/seed/` in place. Record the md5 of `server/storage/app.db` before and after each full test run.

## 1. Schema and role

- [x] 1.1 Schema v8 in `repos/user_store.py`: add `users.role TEXT NOT NULL DEFAULT 'user'`, the `templates` table and a `meta` table (Decision 1, Decision 3), using the column-presence migration, and add `role` to `User`. Verify in `tests/repos/test_user_store.py`:
  - a fresh database is at v8 and new users are `user`;
  - a v7 file with data upgrades with every account `user` and nothing else changed;
  - re-running the migration is a no-op;
  - a half-migrated file (role column present, no templates table) heals.
- [x] 1.2 Add `scripts/set_role.py` (Decision 3), following `set_plan.py`. Verify in `tests/scripts/test_set_role.py`:
  - granting and removing the role;
  - an unknown email exits non-zero and changes nothing;
  - a missing database exits non-zero without creating one;
  - an invalid role is refused;
  - output never contains the email.
- [x] 1.3 Add `require_admin` in `api/deps.py`, giving 403 `admin_required` (Decision 3). Verify in `tests/api/test_deps.py` or a router test:
  - no token gives 401;
  - a user token gives 403 `admin_required`;
  - an admin token passes;
  - a role removed between two requests gives 403 on the second.

## 2. Stored templates and catalog

- [x] 2.1 Add `repos/user_store_templates.py`, a mixin with insert, update, set_retired, get, list_all and the seeded marker, using the store lock. Verify in `tests/repos/test_user_store_templates.py`: a round trip of every field, tags kept in order, retired filtering, and the marker.
- [x] 2.2 Add `seed_templates_if_needed` and build `TemplateCatalog` from stored rows. Put a `CatalogHolder` in `main.py`, with the preview mount from `<STORAGE_ROOT>/template-previews` and the startup orphan sweep (Decisions 1, 2 and 5). Verify in `tests/repos/test_template_catalog.py` and `tests/test_main.py`:
  - a first start imports all 12 seed templates with hashed preview files served at their `preview_url`;
  - a second start with an edited seed ignores it;
  - a start after every template is retired does not re-import;
  - an invalid seed (a duplicate id, a missing preview) fails startup and names the entry;
  - a stored row with a deleted preview file fails startup and names the id;
  - an unreferenced file in `template-previews/` is removed at startup;
  - the existing `GET /templates` order, search and no-prompt tests still pass against the stored catalog.

## 3. Admin service and endpoints

- [x] 3.1 Add `services/template_admin_service.py`, covering validation and screening (Decision 6), preview normalisation (Decision 4), the write order (Decision 5), the lock and catalog swap (Decision 2), and audit logs (Decision 7). Verify in `tests/services/test_template_admin_service.py`:
  - each field limit in the spec, with the field named;
  - a blocked term in the title, a tag or the prompt, with the field named and nothing written;
  - preview: 1200×800 JPEG becomes 512×512 WebP; 3 MB is refused; text named `.png` is refused; GIF is refused; a decompression bomb is refused;
  - a replaced preview gets a new file name and the old file is deleted;
  - a failed commit leaves no new file and no row change;
  - retire and restore are idempotent;
  - two concurrent edits serialise;
  - log lines contain the action, id and admin id, with no prompt, title, tags or email (`caplog`).
- [x] 3.2 Add `api/admin_templates.py` (Decision 8) and register it in `main.py`. Verify in `tests/api/test_admin_templates.py`, using the app factory, a temporary storage root and an admin and a user account:
  - every endpoint's success and error codes from the API summary table;
  - a created template appears in `GET /templates` on the next request and a generation with its id is accepted;
  - an edited prompt is used by the next generation, while a job accepted before the edit (stub pipeline held open) keeps the old one;
  - a retired template is missing from `GET /templates` and `?q=`, and `POST /generations` with it gives 400 `invalid_template`;
  - a job running when its template is retired still succeeds;
  - restore brings it back unchanged;
  - `GET /admin/templates` includes prompts and retired templates last;
  - `GET /templates` still never includes `prompt`.

## 4. Documentation

- [ ] 4.1 In `server/README.md`, document the admin role and `set_role.py`, every admin endpoint with a curl example (multipart create with a preview, patch, retire, restore), the error codes, the one-time seed import, and where previews live now. Verify by running each curl example against a local server on a temporary storage root during 5.2, and by checking that the README names no real email.

## 5. Integration and hand-off

- [x] 5.1 Run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` in `app/` once to confirm the app is unaffected. Verify that all tests pass, that `openspec validate add-template-admin --strict` passes, and that the md5 of `server/storage/app.db` is unchanged.
- [ ] 5.2 **Manual. Local server in log mode on a temporary storage root**, with an upgraded copy of a v7 `app.db` (never the real one):
  - start the server and check that the 12 seed templates are listed;
  - grant admin with `set_role.py`;
  - run every README curl example;
  - in the iOS simulator or Android emulator, see a new template appear and a retired one disappear when home reloads its list (no server restart), and Make another on a creation of a retired template show "Could not load this template.";
  - check the log lines for each change carry no prompt text.

  This box stays unticked until someone runs it. Name any skipped step in the PR.
- [x] 5.3 Push `feat/add-template-admin`. Verify with `git log origin/feat/add-template-admin -1` that it matches the local HEAD.
