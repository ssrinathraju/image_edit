# Design

## Context

`TermMatcher.matches` (`server/src/image_edit_server/core/safety.py`) works in two steps:
1. It pads the normalised prompt with spaces and looks for ` term ` among all terms. That gives whole-word and whole-phrase matches.
2. It finds runs of single letters separated by spaces (`(?<![a-z])[a-z](?: [a-z])+(?![a-z])`), joins each run, and looks for every single-word term as a substring of the joined run.

Normalisation already turns `N-U-D-3` into `n u d e`. `tests/core/test_safety.py` covers spelled-out terms, a one-letter word beside them, and phrase terms not matched in runs.

## Decisions

### Decision 1: Describe the code in the spec; don't change the matcher (user's choice, option A)
**Rejected: narrowing the code so a joined run must equal a term exactly.** That stops the `g r a p e` false alarm. But `a N-U-D-3 woman` joins to `anude` and would then get through. Spelling a term out next to a one-letter word is a common way round filters, while typing a harmless word letter by letter is rare in real prompts.

### Decision 2: Keep the spec wording behavioural
The spec states the rule: runs of two or more single letters, joined, with single-word terms matched anywhere inside. It does not name the regex or the code. It records the trade-off in one sentence, so a later reader knows the false positive is intended.

## Risks and trade-offs

- **Data stored, who can read it, logging:** no change. Blocked prompts are still not echoed or logged.
- **Migration:** none.
- **Failure and retry:** a user whose prompt is blocked by a spelled-out false positive gets the existing `prompt_blocked` message and can rephrase.
- **Background tasks, thread-safety:** none affected. The matcher is immutable.
- **Accepted false positive:** a prompt that spells out a harmless word containing a blocked term, letter by letter, is refused.
