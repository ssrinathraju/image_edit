# Follow-ups

Items deferred from PR #1 review. None block the merge.

## Deferred

- [ ] **Android release pass** — polish, not a bug:
  - Recover lost data after the activity is killed (image picker / camera).
  - Camera "permission denied" path that offers to open Settings.
- [ ] **`resolveUrl` with absolute URLs** — only matters once results are served from a CDN. Revisit then.
- [ ] **Friendly text for failed jobs** — the status screen shows the server's raw code (e.g. `pipeline_failed`). Map known codes to user-facing messages. Predates PR #1.
- [ ] **Search text as prompt** — search text isn't capped when reused as the prompt. Cosmetic: the custom screen already shows the 500-character error.
- [ ] **`assert` stripped in release builds** — low value, the server already returns a clean 400. Replace with an explicit check if we touch that code.
- [ ] **Image format sniffing helper** (`app/lib/services/image_actions.dart`) — builds a list and `asMap()` per check. Simplify with a plain byte comparison.

## Decided, no change

- Multi-face removal: intentional. The spec's REMOVED requirement and the PR notes cover it.
