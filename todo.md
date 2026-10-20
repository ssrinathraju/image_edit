# Follow-ups

Items deferred from PR #1 review. None block the merge.

## Manual testing log

- **2026-10-20 — iOS simulator pass (by the user), all current flows OK:** against a local log-mode server on a temporary storage root. Covered: register with the age gate and emailed code, sign in and out, password reset (the code appears once the 60-second per-address limit has passed), template and custom generation, the consent screen (decline, accept, withdraw), My creations (grid, detail, download, share, delete), referrals, the profile, and a second account. **Not covered:** a pre-upgrade `app.db`, the Android emulator and APK build, the backup-exclusion checks, real SMTP, and anything needing the Google or Apple consoles. Archived task boxes stay unticked, because each one bundles steps outside this run. What is still open is listed in the items below.

## Deferred

- [ ] **Android release pass** — polish, not a bug:
  - Recover lost data after the activity is killed (image picker / camera).
  - Camera "permission denied" path that offers to open Settings.
- [ ] **`resolveUrl` with absolute URLs** — only matters once results are served from a CDN. Revisit then.
- [ ] **Search text as prompt** — search text isn't capped when reused as the prompt. Cosmetic: the custom screen already shows the 500-character error.
- [ ] **`assert` stripped in release builds** — low value, the server already returns a clean 400. Replace with an explicit check if we touch that code.
- [ ] **Image format sniffing helper** (`app/lib/services/image_actions.dart`) — builds a list and `asMap()` per check. Simplify with a plain byte comparison.

## From PR #2 review (auth and profile)

- [ ] **Authenticated or signed image URLs** — `/images/<job_id>.png` is public to anyone holding the URL. Job ids are unguessable but time-ordered. Needed before any public deployment.
- [ ] **Deep links lost on the login redirect** — the router sends a signed-out user to `/login` and forgets the target. Polish for when the app has real deep links.

## From enforce-output-retention

- [ ] **Tell users when a result expires** — add `expires_at` to the status response and a note on the result screen. Results are deleted after the retention period (24 hours by default) with no warning today; Download and Share are the only way to keep one.

- [x] **`generation_service.submit` ignores the app's settings** — it takes its settings from a module-level `Settings()` default and the router never passes the app's own settings. With an app built from an explicit `Settings(...)`, reference-face uploads and the validation limits (`MAX_FACES`, `MAX_UPLOAD_BYTES`, prompt length, accepted types) come from the environment default instead, so uploads land in `./storage/inputs` while the worker deletes under the configured root. Dormant in a normal deployment because both read the same environment variables. Visible in tests: every test run leaves face folders in the real `server/storage/inputs`. Fix: provide the app's settings to the generations router through a dependency and use them in `submit`, with a test that an explicit storage root receives the upload.

## From archive

- [ ] **Remaining steps of the early manual passes** — the iOS simulator flows were checked on 2026-10-20 (see the log above). Still unconfirmed:
  - add-trending-templates 9.2: the specific search ("beach"), Retry and Download-to-Photos steps;
  - add-auth-and-profile 11.2: the cross-account `curl` 404 check and deleting the second account;
  - add-plans-and-referrals 10.2: the upgrade of a data-bearing `app.db` copy, the limit dialog after 3 generations, and promoting an account with `set_plan.py`.

  The archived boxes stay unticked until these are run.

## From PR #4 review (plans and referrals)

- [ ] **Referral farming (remaining risk)** — verification now gates the referral reward, but disposable email addresses still pass and there are no per-IP limits on registration. Add disposable-domain screening or per-IP limits before any public launch.
- [ ] **Hide the Upgrade entry in release builds** until billing exists (the screen is a "payments not available" placeholder).
- [ ] **Duplicate `/me` fetch at startup** — session restore and `AccountNotifier` each call it.
- [ ] **Failed settle gives a free generation** — if settling fails after a success, the reservation is refunded at the next restart. Rare and logged; accepted.

## From add-content-safety

- [ ] **Tune the threshold and the term list before launch** — `SAFETY_NSFW_THRESHOLD` (0.7) and `seed/safety/blocked_terms.txt` are a starting point. Run real generations (swimwear and beach templates especially) and adjust, then have the starter list reviewed.
- [ ] **Starter-list false positives and normalisation gaps** — the list blocks "nude-colored dress", "gore-tex jacket", "topless convertible car" and "loli pop". Zero-width characters (`n\u200bude` becomes "n ude") and Cyrillic look-alike letters slip past `normalize_text`. Handle both when tuning.
- [ ] **Design drift to correct at archive** — design.md Decision 1 describes the joined-letter check as joining every single-letter run and matching whole words; the code now tests each single-word term as a substring of each spelled-out run (so "a N-U-D-3 woman" is caught). The design's logging list names a `strike` event; the worker logs only `output_blocked`, and the README matches the code.
- [ ] **Device report images are always saved as `<id>.png`** even when the upload was JPEG (harmless; `show --out` writes the bytes under the operator's name).
- [ ] **Paused-dialog test does not exercise the local-time conversion** — it computes the expected time with `toLocal()` in the test's own timezone; set a non-UTC zone to prove it.
- [ ] **Reported images in the privacy review** — reports keep a face-derived image for 30 days, longer than the 24-hour result retention. Add this to the privacy policy review.

## Deployment checklist

- [ ] **Cap the request body size at the proxy** — the multipart body of `POST /generations` is received by the framework before the handler runs. The quota pre-check saves the read and decode, not the transfer, so the proxy should refuse bodies above the 40 MB total.

## Decided, no change

- Multi-face removal: intentional. The spec's REMOVED requirement and the PR notes cover it.
- Per-email lockout can be abused and the throttle is per process: accepted trade-offs in the auth design (Decision 4).
- Stale state on a fresh sign-in: unreachable, the router redirects signed-in users away from `/login`.

## From PR review of add-email-verification-and-reset (round 2)

- [ ] **FastAPI `BackgroundTasks` in `auth_service`** — pass a plain `schedule: Callable` to keep the services layer framework-free. Follows the existing `HTTPException` pattern, so deferred.
- [ ] **README warning for `SMTP_SECURITY=none` with a username** — the SMTP password is sent in clear text.
- [ ] **Server venv is Python 3.9.6** while CLAUDE.md says 3.11+ (pre-existing).
- [ ] **Remaining manual checks for add-email-verification-and-reset** — the current registration and reset flows passed on the iOS simulator on 2026-10-20. Still open: 11.2's pre-upgrade `app.db` step (its Verify-email steps were superseded by add-social-sign-in's registration rework), and 11.3, a real SMTP send.

## From add-social-sign-in

- [ ] **Encrypt the stored Apple refresh token** — `identities.apple_refresh_token` is plain text in `app.db`. Someone holding the database can use it only to get Apple tokens that identify the user to this app, but encrypting it needs a key-management design.
- [ ] **Sign in with Apple entitlement blocks signed device builds until the Apple Developer membership exists** — `app/ios/Runner.xcodeproj/project.pbxproj` sets `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements` for Debug, Release and Profile, and a free Personal Team cannot sign `com.apple.developer.applesignin`. The simulator and `--no-codesign` builds are unaffected. Documented in `server/README.md` (device note after the console checklist). Confirm on a device during the manual pass (14.3, never recorded, see the item below), and move the entitlement to a Release-only configuration if development devices must keep working before the membership.
- [ ] **Remaining manual checks for add-social-sign-in** — 14.2's registration flows passed on the iOS simulator on 2026-10-20. Still open: 14.2's pre-upgrade `app.db` step (an unverified account still signs in and can generate), and 14.3 (real Google/Apple sign-in; needs the consoles, App ID and key, and also covers the device-signing check in the entitlement item above).
- [ ] **Mutual referral redemption** — two fresh provider accounts can redeem each other's codes (each gets +5 once, within 24 hours of creation). Bounded by the referrer cap and by the one-redemption-per-account rule. Closing it needs a rule such as "a code from an account that itself redeemed in the last 24 hours is refused", which is a spec change. Part of the wider referral-farming item above (disposable emails, no per-IP limits).

- [ ] **Confirm screen `_backToRegistration` fallback loses typed values** — `context.go('/register')` opens a fresh screen when Confirm is the root route; unreachable in normal flow.

## From add-on-device-history

- [ ] **Remaining manual checks for add-on-device-history** — 8.2's iOS simulator flows passed on 2026-10-20. Still open: 3.2 (the Android build and merged-manifest check; needs the Android SDK), 8.2's Android emulator half, and 8.3 (the backup-exclusion check on iOS and Android).

## From add-age-gate-and-face-consent

- [ ] **Legal review of the consent wording** — have the face-photo consent text (`features/consent/consent_text.dart`) and the privacy policy reviewed for GDPR and BIPA before launch; bump `CONSENT_VERSION` when the text changes.
- [ ] **Spec follow-up** — add the 'Update the app to continue' behaviour for an unknown consent version to the account-ui spec through a /prod-pm change (CLAUDE.md forbids editing openspec/specs directly; archive only syncs this change's deltas).
- [ ] **Router notes** — `ageConfirmed ?? true` (router.dart) and the `/me`-fails-to-load case send an unconfirmed user home until the server answers `age_not_confirmed`; a future `ref.invalidate(accountProvider)` would redirect through the splash screen mid-flow. Add `/referral-prompt` and `/confirm-registration` to the router test's list of routes an unconfirmed account cannot open.
- [ ] **Remaining manual checks for add-age-gate-and-face-consent** — 7.2's iOS simulator flows (the under-18 refusal, consent decline and accept, withdraw) passed on 2026-10-20. Still open: 7.2's pre-upgrade `app.db` step (Confirm your age, and the blocked screen), 7.3 (the consoles), and the reviewer's extra manual checks: a pending registration across the upgrade, an unknown consent version, a version change while the consent screen is open, and the date-of-birth transport limit.

## From harden-server-edge-cases

- [ ] **Manual check 4.2 never run** — the iOS simulator check (the limit dialog appears at once after 3 generations, and generation works normally before the limit) was not run for harden-server-edge-cases. The plain-language failure text is covered by widget tests only, because the stub pipeline cannot be made to fail.
