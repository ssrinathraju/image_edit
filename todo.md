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

- [ ] **Failed jobs' records are never swept** — a failed job has no image, so the sweep never finds it and its (small) in-memory record lives until the process restarts. Give jobs a finish time and expire terminal records older than the retention period regardless of image; this needs a one-line spec addition. Accepted for now: growth is slow and bounded by restarts.
- [x] **`generation_service.submit` ignores the app's settings** — it takes its settings from a module-level `Settings()` default and the router never passes the app's own settings. With an app built from an explicit `Settings(...)`, reference-face uploads and the validation limits (`MAX_FACES`, `MAX_UPLOAD_BYTES`, prompt length, accepted types) come from the environment default instead, so uploads land in `./storage/inputs` while the worker deletes under the configured root. Dormant in a normal deployment because both read the same environment variables. Visible in tests: every test run leaves face folders in the real `server/storage/inputs`. Fix: provide the app's settings to the generations router through a dependency and use them in `submit`, with a test that an explicit storage root receives the upload.

## From archive

- [ ] **Manual device pass not recorded** — the full manual simulator checklist for trending templates (add-trending-templates 9.2) and auth/profile (add-auth-and-profile 11.2) was not recorded. Only registration and sign-in against the real server were confirmed. Both tasks are left unchecked in the archived `tasks.md`.
- [ ] **Plans/referrals manual device pass not recorded** — the manual simulator pass for add-plans-and-referrals (10.2) was not recorded, including upgrading a copy of a real data-bearing `app.db` and the full referral flow (register with a code, both accounts +5, generate with bonus, limit dialog, promote with `set_plan.py`). Left unchecked in the archived `tasks.md`.

## From PR #4 review (plans and referrals)

- [ ] **Referral farming (remaining risk)** — verification now gates the referral reward, but disposable email addresses still pass and there are no per-IP limits on registration. Add disposable-domain screening or per-IP limits before any public launch.
- [ ] **Hide the Upgrade entry in release builds** until billing exists (the screen is a "payments not available" placeholder).
- [ ] **Unknown plan returns 500** — `daily_limit` raises for a plan value outside `free`/`premium` (only reachable through a corrupted DB). Fall back to Free and log.
- [ ] **Uploads are read before the quota check** — an over-limit user still makes the server read up to 40 MB before the 429.
- [ ] **Duplicate `/me` fetch at startup** — session restore and `AccountNotifier` each call it.
- [ ] **Failed settle gives a free generation** — if settling fails after a success, the reservation is refunded at the next restart. Rare and logged; accepted.

## Decided, no change

- Multi-face removal: intentional. The spec's REMOVED requirement and the PR notes cover it.
- Per-email lockout can be abused and the throttle is per process: accepted trade-offs in the auth design (Decision 4).
- Stale state on a fresh sign-in: unreachable, the router redirects signed-in users away from `/login`.

## From PR review of add-email-verification-and-reset (round 2)

- [ ] **FastAPI `BackgroundTasks` in `auth_service`** — pass a plain `schedule: Callable` to keep the services layer framework-free. Follows the existing `HTTPException` pattern, so deferred.
- [ ] **README warning for `SMTP_SECURITY=none` with a username** — the SMTP password is sent in clear text.
- [ ] **Server venv is Python 3.9.6** while CLAUDE.md says 3.11+ (pre-existing).
- [ ] **Manual passes never recorded for add-email-verification-and-reset** — tasks 11.2 (iOS simulator pass) and 11.3 (optional real SMTP send) were not run.

## From add-social-sign-in

- [ ] **Encrypt the stored Apple refresh token** — `identities.apple_refresh_token` is plain text in `app.db`. Someone holding the database can use it only to get Apple tokens that identify the user to this app, but encrypting it needs a key-management design.
- [ ] **Sign in with Apple entitlement blocks signed device builds until the Apple Developer membership exists** — `app/ios/Runner.xcodeproj/project.pbxproj` sets `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements` for Debug, Release and Profile, and a free Personal Team cannot sign `com.apple.developer.applesignin`. The simulator and `--no-codesign` builds are unaffected. Documented in `server/README.md` (device note after the console checklist). Confirm on a device during the manual pass (14.3, never recorded, see the item below), and move the entitlement to a Release-only configuration if development devices must keep working before the membership.
- [ ] **Manual passes never recorded for add-social-sign-in** — tasks 14.2 (iOS simulator pass, including the pre-upgrade `app.db` check) and 14.3 (real Google/Apple sign-in; needs the consoles, App ID and key, and also covers the device-signing check in the entitlement item above) were not run.
- [ ] **Mutual referral redemption** — two fresh provider accounts can redeem each other's codes (each gets +5 once, within 24 hours of creation). Bounded by the referrer cap and by the one-redemption-per-account rule. Closing it needs a rule such as "a code from an account that itself redeemed in the last 24 hours is refused", which is a spec change. Part of the wider referral-farming item above (disposable emails, no per-IP limits).

- [ ] **Confirm screen `_backToRegistration` fallback loses typed values** — `context.go('/register')` opens a fresh screen when Confirm is the root route; unreachable in normal flow.

## From add-on-device-history

- [ ] **Manual passes never recorded for add-on-device-history** — tasks 3.2 (Android build and merged-manifest check, no Android SDK), 8.2 (simulator/emulator pass) and 8.3 (backup-exclusion check) were never run.

## From add-age-gate-and-face-consent

- [ ] **Legal review of the consent wording** — have the face-photo consent text (`features/consent/consent_text.dart`) and the privacy policy reviewed for GDPR and BIPA before launch; bump `CONSENT_VERSION` when the text changes.
- [ ] **Non-string date of birth gets 422, not 400** — the age spec says anything other than `YYYY-MM-DD` is `400 invalid_date_of_birth`; a JSON number for `date_of_birth` still fails pydantic's `string_type` with 422. Strings of any plausible length now get 400 (limit raised to 32). Amend the spec delta to allow 422 for non-string input, or accept `Any` and check it in `check_date_of_birth`.
- [ ] **Design text drift at archive time** — `RegistrationDraft.dateOfBirth` stays in memory until the draft is cleared (confirm, back, sign-out), not only while the screen is open; the app shows "Update the app to continue" (no Accept) for a consent version it has no text for. Record both in design.md/specs when archiving.
- [ ] **Router notes** — `ageConfirmed ?? true` (router.dart) and the `/me`-fails-to-load case send an unconfirmed user home until the server answers `age_not_confirmed`; a future `ref.invalidate(accountProvider)` would redirect through the splash screen mid-flow. Add `/referral-prompt` and `/confirm-registration` to the router test's list of routes an unconfirmed account cannot open.
- [ ] **Split `repos/user_store.py`** (about 975 lines, limit 1000) — move age, consent and identities out in the next change.
