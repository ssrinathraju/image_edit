# image_edit — Project Standards

Standards that apply to **every** change in this repository. If a rule here conflicts with a transient instruction, follow this file and raise the conflict.

Implementation-level coding standards (function/file sizes, naming, types, comments, imports, logging, error messages, test details) live in `.claude/skills/code-standards/SKILL.md`. That skill auto-loads whenever code is being written, edited, or reviewed. This file stays short because it loads every turn — including spec and design sessions where coding details are irrelevant.

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

## 2. Tests co-locate under a mirrored `tests/` tree

For `server/src/image_edit_server/services/foo.py`, tests live at `server/tests/services/test_foo.py`. Same pattern for Dart: `app/test/` mirrors `app/lib/`. Each test lands with the implementation it covers in the same OpenSpec task group — never defer tests to a final "testing" group.

## 3. Simplicity

- **No speculative abstractions.** Three similar lines beats a premature abstraction. Introduce an interface only when a second concrete implementation is already planned.
- **No feature flags for code paths that don't exist yet.**
- **No fallback / validation for scenarios that cannot happen.** Validate at system boundaries; trust internal callers.
- **No backwards-compatibility shims** — this project has no users yet.

## 4. Workflow

- Spec changes go through OpenSpec. Flow: `propose → apply → archive`. Do not edit `openspec/specs/*.md` directly — write a change delta.
- Do not install `torch`, `diffusers`, `transformers`, or any model weights except as part of a specific OpenSpec change that commits to a model pipeline.
- Secrets never land in the repo. `.env` files are gitignored; `.env.example` is checked in.

## 5. When rules bite

If a rule here forces an awkward design, say so explicitly in the PR / proposal rather than quietly violating it. Rules exist to be revisited when they stop paying rent.
