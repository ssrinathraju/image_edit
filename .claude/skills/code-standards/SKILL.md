---
name: code-standards
description: Use when writing or editing Python code in server/, Dart code in app/, when implementing an OpenSpec task-list item, or when reviewing a code diff. Also use when the user asks to lint, review, audit, or clean up code. Enforces project implementation standards — function/file size limits, naming, type hints, comments, imports, logging, error messages, and test details. Do NOT load for pure spec/design/documentation work.
---

# Code Standards

Implementation-level rules for Python in `server/` and Dart in `app/`. For folder structure, the test co-location pattern, OpenSpec workflow, and simplicity rules, see the project-root `CLAUDE.md` — it is already loaded.

## 1. File and function size

- **Function / method body: max 150 lines.** If approaching the limit, extract helpers. Guard clauses and early returns count against this budget — use them to shrink it, not to bypass it.
- **File: max 1000 lines.** If approaching, the file is doing too much. Split by concept, not by arbitrary line count.
- **Nesting: max 3 levels** of nested blocks inside a single function. Prefer early returns over deep `if/else`.
- **One concept per file.** A file named `storage.py` is for storage. If you find yourself adding unrelated helpers, make a new file.

## 2. Naming

- Method and function names describe **what the function does**, not how. `delete_inputs_for_job` beats `cleanup`. `enqueue_generation` beats `handle_request`.
- Boolean-returning functions start with `is_`, `has_`, `can_`, or `should_`.
- Avoid abbreviations unless industry-standard (`url`, `id`, `img` fine; `gnrtn` not).
- Private helpers in Python start with `_`. Dart uses `_` for library-private.

## 3. Types

- **Python:** every public function signature typed. Internal one-liners may skip return types only when the return is a trivial literal. Use `from __future__ import annotations` or Python 3.11+ builtins (`list[str]`, `dict[str, int]`), **not** `typing.List`.
- **Dart:** `strict-casts: true`, `strict-raw-types: true`, `strict-inference: true` in `app/analysis_options.yaml`. No `dynamic` without a comment explaining why.
- Prefer `Protocol` (Python) / abstract classes (Dart) for seams. Only introduce an interface when a second implementation is **planned**, not hypothetical.

## 4. Comments and documentation

- **Public API** (anything imported outside its own file): one-line docstring stating purpose. Longer docstring only when behavior is non-obvious.
- **Internal helpers:** no docstring. The name does the work.
- **Inline comments:** only when the **why** is non-obvious — a hidden invariant, a workaround for a specific bug, surprising behavior. Never explain **what** the code does; well-named identifiers already do that.
- **Delete dead code.** Commented-out blocks are prohibited. Git history is the archive.

## 5. Constants, imports, logging, errors

- **No magic numbers or magic strings in logic.** Pull them from `configs/` or declare `MODULE_LEVEL_CONSTANTS` at the top of the file. Spec limits like `MAX_FACES` and `MAX_PROMPT_CHARS` live in `configs/settings.py`.
- **No wildcard imports** (`from x import *`). Dart: no `export '...'` without an explicit `show` list.
- **No `print()` debugging.** Python: `logging` with a module-level logger (`logger = logging.getLogger(__name__)`). Dart: `package:logging`.
- **Errors are actionable.** `raise HTTPException(400, {"error": "invalid_face_count", "detail": "expected 1..4, got 5"})` beats `raise HTTPException(400, "Invalid input")`. The caller must know how to fix it.
- **No bare `except:` or `except Exception:` without re-raising or logging the full context.**

## 6. Test details

Co-location pattern (`server/tests/<mirror>/test_<name>.py`) is in `CLAUDE.md`. Beyond that:

- Prefer `pytest` fixtures over setup/teardown classes. Dart: `test` / `flutter_test`.
- Every failing scenario in an OpenSpec spec MUST map to a test case; the task-list items already enumerate them.
- Tests MUST be deterministic. Seed any randomness.
- No real network, no real GPU calls, no real filesystem outside a `tmp_path` fixture. Mock or inject.
- Integration tests that span multiple layers (e.g., API → service → repo → worker) live under `server/tests/integration/` with the same mirror discipline below that.

## When this skill does NOT apply

- Writing or editing OpenSpec artifacts (`proposal.md`, `spec.md`, `design.md`, `tasks.md`). Those are planning docs, not code.
- Pure documentation edits (`README.md`, standalone markdown).
- Shell / git / config operations.

If the current turn is spec work, do not load or cite this skill.
