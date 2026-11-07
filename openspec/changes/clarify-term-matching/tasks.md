# Tasks

Work on branch `feat/clarify-term-matching`. Do not push to `main`. No production code changes. Only tests in `server/tests/core/test_safety.py` and `todo.md`. Record the md5 of `server/storage/app.db` before and after the full test run.

## 1. Tests for the clarified rule

- [ ] 1.1 Check `server/tests/core/test_safety.py` against the content-safety delta's scenarios:
  - spelled-out term next to a one-letter word;
  - spelled-out harmless word containing a term (`g r a p e` with `rape` on a test list);
  - ordinary `a bowl of grapes` still allowed;
  - phrase term not matched in a run.

  Add a test for any scenario that is missing, using a `TermMatcher` built from its own term list (not the seed file). Do not change `core/safety.py`. Verify that the new tests pass on the unchanged code, and that `git diff server/src` is empty.

## 2. Tracking

- [ ] 2.1 Remove the `todo.md` item that asks the user to decide on term matching (under "From add-content-safety"). Keep the other content-safety items. Verify with `git diff todo.md`.

## 3. Integration and hand-off

- [ ] 3.1 Run `uv run pytest -q` in `server/`. Verify all tests pass, that `openspec validate clarify-term-matching --strict` passes, and that the md5 of `app.db` is unchanged.
- [ ] 3.2 Push `feat/clarify-term-matching`. Verify with `git ls-remote` that the remote branch matches the local HEAD.
