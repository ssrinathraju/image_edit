# Proposal

## Why

The content-safety spec says a blocked term "SHALL match only as whole words". The code does that, and also joins runs of spelled-out single letters and matches single-word terms inside the joined run. The spec's own scenario ("`N-U-D-3` is caught") already depends on that second rule, so the spec contradicts itself. The small-cleanups branch corrected the README and the docstrings, and left the spec for the user to decide. The user chose to keep the code and describe it in the spec (option A): it catches the common dodge `a N-U-D-3 woman`, at the cost of a rare false alarm on spaced-out letters such as `g r a p e`.

## What Changes

- The `content-safety` requirement "Screen custom prompts against a term list" describes both rules:
  - whole-word and phrase matching;
  - single-word terms matched inside joined runs of two or more single letters. Phrase terms are not matched inside such runs.
- New scenarios, one for each case:
  - the caught case (`a N-U-D-3 woman`);
  - the known false positive (`g r a p e`);
  - the ordinary word that is still allowed (`a bowl of grapes`);
  - the phrase that is not run-matched.
- Tests: add any of these scenarios that `tests/core/test_safety.py` does not already cover. No production code changes.
- `todo.md`: remove the "decision for the user" item on term matching.

Out of scope: changing the matcher, editing the term list (that is the separate "tune the term list" item), and the normalisation gaps (zero-width characters, Cyrillic look-alikes), which stay in `todo.md`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `content-safety`: the term-matching rule now states the spelled-out-letter behaviour.

## Impact

- `openspec/` (through archive), `server/tests/core/test_safety.py` (tests only), and `todo.md`. No server or app code changes, and no behaviour changes.
