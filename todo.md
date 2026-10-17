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

## From PR #2 review (auth and profile)

- [ ] **Authenticated or signed image URLs** — `/images/<job_id>.png` is public to anyone holding the URL. Job ids are unguessable but time-ordered. Needed before any public deployment.
- [ ] **Deep links lost on the login redirect** — the router sends a signed-out user to `/login` and forgets the target. Polish for when the app has real deep links.

## From enforce-output-retention

- [ ] **Tell users when a result expires** — add `expires_at` to the status response and a note on the result screen. Results are deleted after the retention period (24 hours by default) with no warning today; Download and Share are the only way to keep one.

## From archive

- [ ] **Manual device pass not recorded** — the full manual simulator checklist for trending templates (add-trending-templates 9.2) and auth/profile (add-auth-and-profile 11.2) was not recorded. Only registration and sign-in against the real server were confirmed. Both tasks are left unchecked in the archived `tasks.md`.
- [ ] **Plans/referrals manual device pass not recorded** — the manual simulator pass for add-plans-and-referrals (10.2) was not recorded, including upgrading a copy of a real data-bearing `app.db` and the full referral flow (register with a code, both accounts +5, generate with bonus, limit dialog, promote with `set_plan.py`). Left unchecked in the archived `tasks.md`.

## From PR #4 review (plans and referrals)

- [ ] **Referral farming** — without email verification a tree of throwaway accounts can mint credits. Before any public launch, pay the referrer only after the friend's first successful generation.
- [ ] **Hide the Upgrade entry in release builds** until billing exists (the screen is a "payments not available" placeholder).
- [ ] **Unknown plan returns 500** — `daily_limit` raises for a plan value outside `free`/`premium` (only reachable through a corrupted DB). Fall back to Free and log.
- [ ] **Uploads are read before the quota check** — an over-limit user still makes the server read up to 40 MB before the 429.
- [ ] **Duplicate `/me` fetch at startup** — session restore and `AccountNotifier` each call it.
- [ ] **Failed settle gives a free generation** — if settling fails after a success, the reservation is refunded at the next restart. Rare and logged; accepted.

## Decided, no change

- Multi-face removal: intentional. The spec's REMOVED requirement and the PR notes cover it.
- Per-email lockout can be abused and the throttle is per process: accepted trade-offs in the auth design (Decision 4).
- Stale state on a fresh sign-in: unreachable, the router redirects signed-in users away from `/login`.
