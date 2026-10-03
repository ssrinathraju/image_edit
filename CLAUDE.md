# image_edit — Project Standards

Standards that apply to **every** code change in this repository. If a rule here conflicts with a transient instruction, follow this file and raise the conflict.

## Scope

- `server/` — Python 3.11+, FastAPI, async-first.
- `app/` — Flutter / Dart.
- `openspec/` — planning artifacts. Format rules are owned by OpenSpec itself; this file does not duplicate them.
- `models/` — model weights, gitignored. **Never commit binaries here.**

## 1. Folder structure — layered, not flat

Both `server/src/image_edit_server/` and the Flutter `app/lib/` MUST group by responsibility, not dump everything in the package root. Minimum top-level directories:

| Dir | Owns |
|---|---|
| `configs/` | Settings, env parsing, feature flags. No I/O, no business logic. |
| `api/` | HTTP (FastAPI routers) in `server/`; UI widgets/screens in `app/`. Thin — delegates to `services/`. |
| `services/` | Business logic. Orchestrates `repos/` + `core/`. No framework imports leak above this layer. |
| `core/` | Domain primitives, pure functions, pipeline interfaces. No I/O, no HTTP. |
| `repos/` | Data access — job store, file storage, future DB. Hides the backend behind an interface. |
| `schemas/` | Pydantic/Dart request/response models and domain DTOs. **Not** named `models/` — that name is reserved for ML weights at project root. |

The pipeline interface `GenerationPipeline` lives in `core/`. Its concrete implementations (stub, SDXL, FLUX, ComfyUI) live under `services/pipelines/`.

A file that does not fit any directory above probably doesn't belong in the project. Ask before creating a new top-level dir.

## 2. File and function size

- **Function / method body: max 150 lines.** If approaching the limit, extract helpers. Guard clauses and early returns count against this budget — use them to shrink it, not to bypass it.
- **File: max 1000 lines.** If approaching, the file is doing too much. Split by concept, not by arbitrary line count.
- **Nesting: max 3 levels** of nested blocks inside a single function. Prefer early returns over deep `if/else`.
- **One concept per file.** A file named `storage.py` is for storage. If you find yourself adding unrelated helpers, make a new file.

## 3. Naming

- Method and function names describe **what the function does**, not how. `delete_inputs_for_job` beats `cleanup`. `enqueue_generation` beats `handle_request`.
- Boolean-returning functions start with `is_`, `has_`, `can_`, or `should_`.
- Avoid abbreviations unless they're industry-standard (`url`, `id`, `img` is fine; `gnrtn` is not).
- Private helpers in Python start with `_`. Dart uses `_` for library-private.

## 4. Types

- **Python:** every public function signature typed. Internal one-liners may skip return types only when the return is a trivial literal. Use `from __future__ import annotations` or Python 3.11+ builtins (`list[str]`, `dict[str, int]`), **not** `typing.List`.
- **Dart:** `strict-casts: true`, `strict-raw-types: true`, `strict-inference: true` in `app/analysis_options.yaml`. No `dynamic` without a comment explaining why.
- Prefer `Protocol` (Python) / abstract classes (Dart) for seams. Only introduce an interface when a second implementation is **planned**, not hypothetical.

## 5. Comments and documentation

- **Public API** (anything imported outside its own file): one-line docstring stating purpose. Longer docstring only when behavior is non-obvious.
- **Internal helpers:** no docstring. The name does the work.
- **Inline comments:** only when the **why** is non-obvious — a hidden invariant, a workaround for a specific bug, surprising behavior. Never explain **what** the code does; well-named identifiers already do that.
- **Delete dead code.** Commented-out blocks are prohibited. Git history is the archive.

## 6. Constants, imports, logging

- **No magic numbers or magic strings in logic.** Pull them from `configs/` or declare `MODULE_LEVEL_CONSTANTS` at the top of the file. The spec limits (`MAX_FACES`, `MAX_PROMPT_CHARS`, etc.) live in `configs/settings.py`.
- **No wildcard imports** (`from x import *`). Dart: no `export '...'` without an explicit `show` list.
- **No `print()` debugging.** Python: `logging` with a module-level logger (`logger = logging.getLogger(__name__)`). Dart: `package:logging`.
- **Errors are actionable.** `raise HTTPException(400, {"error": "invalid_face_count", "detail": "expected 1..4, got 5"})` beats `raise HTTPException(400, "Invalid input")`. The caller must know how to fix it.
- **No bare `except:` or `except Exception:` without re-raising or logging the full context.**

## 7. Tests

- **Co-located under `tests/` mirror.** For `server/src/image_edit_server/services/foo.py`, tests live at `server/tests/services/test_foo.py`. Same pattern for Dart: `app/test/` mirrors `app/lib/`.
- Each test group lands with the implementation it covers (same OpenSpec task group). Do **not** defer tests to a final "testing" group — tests prove the current slice works before the next slice depends on it.
- Prefer `pytest` fixtures over setup/teardown classes. Dart: `test` / `flutter_test`.

## 8. Simplicity rules

- **No speculative abstractions.** Three similar lines of code beats a premature abstraction. Introduce an interface only when a second concrete implementation is already planned (example: `JobStore` with planned Redis/SQLite impl is justified; `UserFormatter` with one impl is not).
- **No feature flags for code paths that don't exist yet.** Add the flag when the second path arrives.
- **No fallback/validation logic for scenarios that cannot happen.** Validate at system boundaries (HTTP input, external API responses). Trust internal callers.
- **No backwards-compatibility shims** before there is anything to be backwards-compatible with. This project has no users yet.

## 9. Workflow

- Spec changes go through OpenSpec. The flow is `propose → apply → archive`. Do not edit `openspec/specs/*.md` directly — write a change delta.
- Do not install `torch`, `diffusers`, `transformers`, or any model weights except as part of a specific OpenSpec change that commits to a model pipeline. The server runs with a stub pipeline until that change arrives.
- Secrets never land in the repo. `.env` files are gitignored; `.env.example` is checked in.

## 10. When these rules bite

If a rule here forces an awkward design, say so explicitly in the PR / proposal rather than quietly violating it. Rules exist to be revisited when they stop paying rent.
