# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour. The current state that matters here:

- **Registration** is two steps. `POST /auth/register` validates the input, stores a `pending_registrations` row (email, password hash, referral code, `created_at`) and emails a code. `POST /auth/register/confirm` (email, code, password) creates the user from the pending row in `complete_registration`.
- **Provider sign-in.** `AuthService.sign_in_with_provider` verifies the token, then calls `SqliteUserStore.sign_in_with_identity`. That returns the linked user, links by email, or inserts a user (`_insert_provider_user`), all in one transaction under `self._lock`. For Apple, the authorization code is exchanged only after that call returns.
- **The store** is at schema version 4, and `_migrate()` adds missing columns by checking `PRAGMA table_info`.
- **Generation submit.** `generation_service.submit` validates face count, uploads and prompt, then reserves quota.
- **The app's routing** is a redirect function in `router.dart` driven by `sessionProvider`, plus flags such as `justCreatedViaProvider`. `AccountNotifier` loads `/me`, and `submit_flow.dart` runs submissions.

## Goals / Non-Goals

**Goals:**
- No account is ever created for someone who said they are under 18, and no date of birth is ever stored.
- Every generation is preceded by consent to the current version, enforced on the server, not just in the app.
- One age rule, as a pure function, shared by every path.

**Non-Goals:**
- Proving age: there's no ID check, and the date is self-declared.
- Keeping a history of consent changes. Only the latest state is kept.
- Changing referral rules or the order of the referral prompt.

## Decisions

### 1. The age rule is one pure function in `core/age.py`
`check_date_of_birth(text, today) -> None` raises `InvalidDateOfBirth` or `UnderAge`. The steps:
1. Parse strictly with `date.fromisoformat` after checking the pattern `^\d{4}-\d{2}-\d{2}$`, which rejects `2008-1-1` and datetimes.
2. Reject a date after `today`.
3. Compute the 18th birthday as `birth.replace(year=birth.year + 18)`. A 29 February birth that hits `ValueError` uses 1 March of that year.
4. The person is adult when `today >= eighteenth`.

`today` is the injected clock's UTC date, so tests can fix it.

- **Alternative rejected: computing in the app.** The server must enforce the rule anyway, and two copies drift apart.
- **Alternative rejected: using the user's local date.** The server doesn't know the time zone. Using UTC can make someone on their 18th birthday wait up to about 14 hours, which is accepted.

### 2. Storage: three columns, schema version 5
- `users.age_confirmed_at TEXT NULL`
- `users.consent_version TEXT NULL`
- `users.consent_at TEXT NULL`

`_migrate()` adds them when they are missing. Existing rows get NULL, which gives "existing accounts are unconfirmed". `SCHEMA_VERSION = 5`. Upgrading from a schema below 5 also deletes `pending_registrations`, so registrations started before the age check must be started again. The `User` dataclass gains `age_confirmed` (`age_confirmed_at is not None`), `consent_version` and `consent_at`.

The date of birth is never a column and never logged. Request models hold it only for the life of the request.

- **Alternative rejected: storing the birth year.** It isn't needed for an 18+ gate, and it is still personal data.

### 3. Registration carries the age check
- `POST /auth/register` gets its own request model, `RegisterRequest` (`Credentials` plus a required `date_of_birth: str`, max length 32; a longer or non-string value gets 422). `Credentials` is shared with login, which must not require a date. A missing field is pydantic's 422, which the spec covers as "an error".
- The auth service's registration method calls `check_date_of_birth` first, before email, referral or limit checks. `InvalidDateOfBirth` becomes 400 `invalid_date_of_birth` and `UnderAge` becomes 400 `under_age`.
- Nothing is stored for a refused request. Every pending registration has therefore passed the check, so `complete_registration` sets `age_confirmed_at = now` when it inserts the user. No new pending column is needed.

### 4. Provider sign-up asks before creating
`GoogleSignInRequest` and `AppleSignInRequest` gain an optional `date_of_birth`.
- **The service** checks the date's format up front, if one is present, so a malformed date is 400 `invalid_date_of_birth` even for existing accounts.
- **The store.** `sign_in_with_identity` gains a parameter `adult_confirmed: Optional[bool]`: None when no date was sent, otherwise the result of the age check. In step 4 (create), inside the same transaction:
  - None raises `AgeRequired`;
  - False raises `UnderAge`;
  - True inserts the user with `age_confirmed_at = now`.

  Steps 1–3 (a linked identity, or linking by email) ignore it. That gives "existing accounts are not asked".
- **The service** maps `AgeRequired` to 400 `age_required` and `UnderAge` to 400 `under_age`. Because the exception is raised before the Apple code exchange, the code is never used, and the app can resend the same Apple credential.
- **Linking by email to an existing unconfirmed account** links it and signs in. That account then meets the Confirm your age screen, like every existing account.

- **Alternative rejected: create the account and gate it afterwards.** A minor's account would exist, briefly or until deleted. The user chose to ask first.

### 5. `/me` endpoints for age and consent
- **`POST /me/age {date_of_birth}`:**
  - an already confirmed account gets 409;
  - otherwise the age is checked, and under 18 gets 403 `under_age`;
  - otherwise `age_confirmed_at = now`.
- **`POST /me/consent {version}`:** compared with `settings.CONSENT_VERSION`. A match stores the version and `now`; anything else is 400 `consent_version_mismatch`.
- **`DELETE /me/consent`:** sets both consent columns to NULL and answers 204.
- **`MeResponse`** gains `age_confirmed` and `consent: {accepted_version, accepted_at, current_version}`.

All of these are plain `def` handlers, and each store update is a single UPDATE under the lock.

### 6. The generation gate runs first
The first statements of `generation_service.submit`:
- if the user's age isn't confirmed, raise 403 `age_not_confirmed`;
- otherwise, if `user.consent_version != settings.CONSENT_VERSION`, raise 403 `consent_required`.

These run before face-count validation, before uploads are read and before quota is reserved. That gives the spec's "no job, no stored face, no count".

`User` is loaded fresh for each request by the auth dependency, so a withdrawal takes effect on the next request.

### 7. Settings
- `CONSENT_VERSION: str = "1"`, which must be non-empty (checked at startup). Changing it is how a revised consent text is rolled out.
- The minimum age, 18, is a constant in `core/age.py`, not a setting, because lowering it would need a different product and legal review.

### 8. App flows
- **Register:** a date-of-birth field opens `showDatePicker`, with `lastDate` today and `initialDate` 18 years ago. It's sent as `YYYY-MM-DD`. The under-age message comes from the server's `under_age`.
- **Provider sign-up:** in `provider_buttons.dart`, `age_required` pushes `/age` with the pending `ProviderCredential` held in memory. Continue resends the same credential plus the date. `under_age` shows the message and pops to sign-in; cancelling also pops. The credential is dropped when the screen closes.
- **Existing accounts:** the router redirect checks `accountProvider`. A signed-in account with `age_confirmed == false` goes to `/confirm-age`, and every other signed-in route redirects there until it is confirmed.
  - An under-18 answer shows `/age-blocked`, which offers Delete account (the existing flow) and Sign out.
  - While the account is loading, the redirect waits on the splash screen, as it already does for the session.
- **Consent:**
  - `submit_flow.dart` checks `account.consent.acceptedVersion == account.consent.currentVersion` before submitting. If they differ, it pushes the consent screen. Accept calls `POST /me/consent` with `currentVersion`, refreshes the account and continues the submit with the same request. Decline pops and keeps the form.
  - A server 403 `consent_required` opens the same screen and retries once after Accept. A 403 `age_not_confirmed` sends the user to `/confirm-age`.
- **Unknown consent version:** when the app has no text for the current version, the consent screen shows "Update the app to continue" with no Accept. A `consent_version_mismatch` while the screen is open refreshes the account and shows the new text if known, otherwise the same state.
- **Consent text:** placeholder text in `features/consent/consent_text.dart`, keyed by version, with a "Privacy policy" link to `AppConfig.privacyUrl` that is hidden when that isn't configured.
- **Profile:** a Face photo consent row with Withdraw. Withdraw shows a confirmation dialog, calls `DELETE /me/consent` and refreshes the account.

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Register (date field) | Submit spinner | Date empty, Submit disabled | `under_age`: "You must be 18 or older to use this app", other values kept. `invalid_date_of_birth`: "Enter a valid date of birth" | Confirm registration screen, as today |
| Provider date of birth (`/age`) | Continue spinner | Date empty, Continue disabled | `under_age`: the message, then back to sign-in with no session. Other errors: the existing provider messages | Signed in. A new account then sees the referral prompt, as today |
| Confirm your age (`/confirm-age`) | Submit spinner | Date empty, Submit disabled | `under_age`: go to `/age-blocked`. Network: "Couldn't confirm, try again" | Account refreshed, home |
| Age blocked (`/age-blocked`) | Spinner during delete | "This account can't be used because you must be 18 or older." with Delete account and Sign out | Delete errors as on the profile | Sign-in screen |
| Consent | Accept spinner | The text, with Accept and Decline (and the Privacy policy link if configured). For a consent version the app has no text for: "Update the app to continue", with no Accept | `consent_version_mismatch` (the version changed while the screen is open): refresh the account and show the new text if the app has it, otherwise the "Update the app to continue" state. Network: a retry message | The submission continues to the status screen |
| Profile consent row | Hidden while the account loads | "Not given" | Withdraw failure: SnackBar | "Given on <date>" with Withdraw, or "Not given" after withdrawing |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - Per account: `age_confirmed_at`, `consent_version` and `consent_at`, kept as long as the account and removed with it.
  - **No date of birth is stored anywhere**: not on the server, in logs, or on the device. The app holds it in memory only: on the registration draft (with the password) until the draft is cleared on confirm, back or sign-out, so Resend can send it again, and on the provider date screen while it is open. It is never persisted.
  - Withdrawing consent clears its two columns, and no history is kept.
- **[Who can read it]** Only the account itself, through `/me`. Nothing is exposed to other users.
- **[What is logged]**
  - Under-age refusals are logged with the event name only: no email, no date, no user id for sign-ups. The aim is that a refused minor leaves no personal data behind.
  - Consent changes are logged with the user id, the version and the action.
- **[Existing data and migration]**
  - Schema v5 adds three nullable columns in one transaction, and it is idempotent. Pending registrations from before the upgrade are deleted.
  - Every existing account becomes unconfirmed without consent and is asked on next use. That's acceptable because there is only development data.
  - Rollback: the v4 server ignores the extra columns.
- **[Self-declared age]** Anyone can enter a false date, and that can't be prevented without ID checks, which are out of scope. Stores and regulators generally accept a self-declared age gate for an 18+ rating. Nothing is stored after a refusal, so retrying with another date isn't blocked; the user decided against a device lock.
- **[UTC boundary]** Someone on their 18th birthday may be refused for up to about 14 hours, depending on their time zone. → Accepted.
- **[Consent wording]** The shipped text is a placeholder and must be reviewed for GDPR and BIPA before launch. → Recorded in `todo.md` by task 6.2.
- **[Failure and retry]**
  - A provider sign-up that gets `age_required` is resent with the same token. A Google ID token lasts about an hour and Apple's identity token about 10 minutes. If it has expired, the server answers 401 `invalid_provider_token`, and the app shows the existing "Sign-in failed, try again" so the user taps Continue with Apple again.
  - A consent POST that fails leaves nothing recorded, and the submission isn't sent.
- **[Background tasks when a call raises]** None are added.
- **[Thread-safety of shared state]**
  - The age column and consent columns are each written by one UPDATE under `SqliteUserStore._lock`.
  - The provider create path makes the age decision inside the existing find-link-create transaction, so a concurrent sign-in can't create an account without it.
  - The gate reads the `User` loaded for that request. A withdrawal racing an in-flight submission may let that one submission through, which is accepted.

## Migration Plan

1. Deploy the server and the app together. The old app doesn't send `date_of_birth`, so its registrations would fail validation, and its users would get 403 on generating with no way to give consent.
2. The first start migrates `app.db` to schema version 5.
3. Before launch, replace the placeholder consent text with reviewed wording. Bump `CONSENT_VERSION` whenever the text changes in substance.
4. Rollback: redeploy the previous server and app. The extra columns are ignored.
