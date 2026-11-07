# Tasks

Work on branch `feat/upgrade-server-python`. Do not push to `main`. The work is in `server/`, plus `todo.md`; the app is not changed. "Decision N" refers to `design.md`. Never install the `ml` group. Record the md5 of `server/storage/app.db` before and after each full test run.

## 1. Version

- [x] 1.1 Set `server/.python-version` to `3.11` and `requires-python = ">=3.11"`. Then run `uv python install 3.11` if needed, `uv lock` (no `--upgrade`, per Decision 2) and `uv sync`. Verify:
  - `uv run python --version` prints 3.11.x;
  - `git diff server/uv.lock` shows only changes the new Python version forces, with each version change listed in the report;
  - installing with 3.9 fails: `uv pip install --python 3.9 --dry-run .` or an equivalent check names the required version.

## 2. Code that waited on 3.11

- [x] 2.1 Create the write lock in `TemplateAdminService.__init__` and remove the lazy `_write_lock` helper and its comment (Decision 3). Verify:
  - `tests/services/test_template_admin_service.py` passes, including the two-concurrent-edits test;
  - replacing the lock with a no-op still makes that test fail.
- [x] 2.2 Drop the `int` monkeypatch from the long-popularity test, keeping a real request with a 5000-digit `popularity`. Verify:
  - it answers 400 `invalid_template_field` naming `popularity` on 3.11;
  - temporarily removing the `[0-9]{1,3}` check makes it fail with a 500. This shows the real 3.11 limit is what's being exercised.

## 3. Documentation

- [x] 3.1 In `server/README.md`, state that the server needs Python 3.11 and that `uv sync` installs it. Remove the "Server venv is Python 3.9.6" item from `todo.md`. Verify with `git diff` that only these lines changed.

## 4. Integration and hand-off

- [x] 4.1 On 3.11, run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` once in `app/` to confirm it is unaffected. Verify:
  - all tests pass, with the counts reported;
  - `openspec validate upgrade-server-python --strict` passes;
  - the md5 of `server/storage/app.db` is unchanged.
- [ ] 4.2 **Manual.** On a temporary storage root, start the server with the README command on 3.11. Then:
  - register and confirm an account in log mode;
  - submit a stub generation;
  - grant admin with `set_role.py` and create a template with curl.

  This box stays unticked until someone runs it. It is part of the user's combined manual pass.
- [x] 4.3 Push `feat/upgrade-server-python`. Verify with `git ls-remote origin feat/upgrade-server-python` that it matches the local HEAD.
