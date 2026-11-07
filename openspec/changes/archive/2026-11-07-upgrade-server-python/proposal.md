# Proposal

## Why

`CLAUDE.md` says the server targets Python 3.11+, but `server/.python-version` pins 3.9 and `pyproject.toml` allows `>=3.9`, so every environment and test run so far has used Python 3.9.6. That gap has already cost us:
- template-admin needed a 3.9-only workaround (a lazily created `asyncio.Lock`);
- a 3.11-only behaviour (the integer-string digit limit) could only be tested with a stand-in.

Launch infrastructure should run the version the project says it uses. This goes first of the three launch-readiness changes, so that `sign-result-urls` and `add-abuse-limits` are built and tested on 3.11.

## What Changes

- **Pin and require 3.11:** `server/.python-version` becomes `3.11`, `requires-python` becomes `>=3.11`, and `uv.lock` is re-resolved for it, keeping dependency versions where they still resolve.
- **Remove the 3.9 workaround:** the template admin service's lazily created write lock is created in `__init__`, as Python 3.10+ allows.
- **Real 3.11 test:** the long-popularity test no longer needs to stand in for 3.11's limit; it runs for real.
- **Docs:** `server/README.md` names Python 3.11 in setup (uv installs it). The `todo.md` item "Server venv is Python 3.9.6" is removed.

Out of scope:
- rewriting type hints (`Optional[...]` to `... | None`) or other modernisation across the codebase;
- upgrading dependencies beyond what re-locking for 3.11 requires;
- installing the `ml` group (it is only re-locked, not installed);
- any API or behaviour change.

## Capabilities

### New Capabilities
- `server-runtime`: covers the Python version the server requires, and that validation errors stay validation errors on that version.

### Modified Capabilities
None.

## Impact

- **Server:** `server/.python-version`, `server/pyproject.toml`, `server/uv.lock`, `services/template_admin_service.py` (the lock), its test, and `server/README.md`. Plus `todo.md`.
- **Developers:** run `uv sync` once. uv downloads Python 3.11 if it is missing and recreates `.venv`.
- **App:** unchanged.
