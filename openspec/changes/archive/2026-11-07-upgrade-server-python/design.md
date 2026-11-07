# Design

## Context

- **Version pins:** `server/.python-version` is `3.9`, and `pyproject.toml` has `requires-python = ">=3.9"`. The `.venv` and every test run use 3.9.6.
- **Which Python is available:** uv can install CPython 3.11.17 (and 3.12 to 3.15) on this machine.
- **Code waiting on 3.11:**
  - `services/template_admin_service.py` creates its `asyncio.Lock` lazily, because before 3.10 a lock binds to the loop running when it is created;
  - the long-popularity test monkeypatches `int` to imitate 3.11's 4300-digit limit.

## Decisions

### Decision 1: Pin 3.11 exactly, require `>=3.11`
`.python-version` is `3.11`, which uv resolves to the newest 3.11 patch release. `requires-python` is `>=3.11`.

3.11 is the floor `CLAUDE.md` names. It has the widest wheel support for the `ml` group (torch, diffusers, transformers) and a long security-support window.

**Rejected:** pinning 3.12 or 3.13. That goes beyond what the project standard asks for, with no feature we need, and some ML wheels lag on the newest versions.

### Decision 2: Re-lock without upgrading
Run `uv lock` (not `uv lock --upgrade`) after the version change. Packages keep their locked versions wherever those support 3.11, and only packages whose locked version has no 3.11 support move. The diff of `uv.lock` is checked and listed in the PR.

The `ml` group is re-resolved in the lock but **not installed**, per `CLAUDE.md` §4.

### Decision 3: Remove the lazy lock, keep everything else as it is
`TemplateAdminService.__init__` creates `self._lock = asyncio.Lock()` directly. Its test (two concurrent edits serialise) must still pass, and the lock mutation from the earlier review must still be caught.

The long-popularity test keeps the real 5000-digit request, and the `int` monkeypatch is dropped, since the interpreter now enforces the limit itself.

Nothing else is rewritten.

**Rejected:** a sweep from `Optional[...]` to `| None` and other 3.10+ idioms. It touches most files, mixes noise into a version change, and isn't required (CLAUDE.md §3: no speculative churn).

### Decision 4: How the environment is replaced
`uv sync` recreates `.venv` on the pinned interpreter. Nothing in `server/storage/` depends on the Python version: SQLite files are portable, and `app.db` is untouched.

## Risks and trade-offs

- **Data stored:** none new. `app.db` and the storage folders aren't touched; the md5 of `app.db` is recorded before and after.
- **Who can read it:** unchanged.
- **Logging:** unchanged.
- **Migration:** only for developers' environments; one `uv sync` per checkout. No database migration.
- **Behaviour differences between 3.9 and 3.11:**
  - Any code depending on 3.9-only behaviour would fail the full suite, which must pass on 3.11.
  - The known differences are the integer-string limit (handled already) and the asyncio lock binding (removed above).
  - `datetime` and `zoneinfo` behaviour is the same for the uses here.
- **Failure and retry:** if `uv lock` cannot resolve a dependency for 3.11, the change stops and reports it (BLOCKED). It does not raise the version of unrelated packages to work around it.
- **Background tasks and shared state:** unchanged, apart from the lock now being created eagerly. That is safe on 3.10+, where a lock binds to the running loop on first use, not when it is created.
- **Rollback:** revert the commit and run `uv sync` again.
