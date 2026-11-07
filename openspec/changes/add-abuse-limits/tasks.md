# Tasks

Work on branch `feat/add-abuse-limits`. Do not push to `main`. This builds on `upgrade-server-python`: merge `origin/main` first and run on Python 3.11. "Decision N" refers to `design.md`. Tests use temporary storage roots and fake clocks. Record the md5 of `server/storage/app.db` before and after each full test run. Never log network addresses or full email addresses.

## 1. Disposable emails

- [ ] 1.1 Add `seed/abuse/disposable_domains.txt`. Take a starter list from the CC0 `disposable-email-domains` project, with its source and date in a header comment. Add `core/disposable_domains.py`, and the `DISPOSABLE_DOMAINS_FILE` setting with a startup failure when the file is missing (Decision 1). Verify in `tests/core/test_disposable_domains.py`:
  - a listed domain, a subdomain, upper case, and a domain that only shares a suffix (`notmailinator.com` must pass) all behave correctly;
  - comments and blank lines are ignored;
  - `privaterelay.appleid.com` is not on the list;
  - a missing file fails `create_app` and names the file.
- [ ] 1.2 Refuse disposable addresses in `POST /auth/register` and `POST /me/email`, before anything is stored or sent (Decision 1, Decision 5). Verify in `tests/api/test_auth_register.py` and `tests/api/test_me_security.py`:
  - 400 `disposable_email` with the detail text;
  - no pending registration and no email sent (fake sender);
  - an ordinary domain still works;
  - Google and Apple sign-ins with a relay address are unaffected;
  - the log line has the domain but not the full address (`caplog`).

## 2. Sign-up limit

- [ ] 2.1 Add `core/client_address.py` and the `TRUSTED_PROXY_HOPS` setting (Decision 3). Verify in `tests/core/test_client_address.py`:
  - hops 0 gives the connection address;
  - hops 1 with `spoofed, client` gives `client`;
  - hops 2 picks the right entry;
  - a header shorter than hops falls back;
  - whitespace and an empty header are handled.
- [ ] 2.2 Add `core/signup_limiter.py` (Decision 2). Verify in `tests/core/test_signup_limiter.py`, with a fake clock:
  - the 6th request in an hour is refused, with the correct wait;
  - the 11th in 24 hours is refused, with the correct wait, when fewer than 5 fall in the last hour;
  - refused requests aren't counted;
  - other addresses are independent;
  - entries older than 24 hours are dropped;
  - concurrent `record` calls from threads keep an exact count.
- [ ] 2.3 Apply the limiter to accepted registrations and to provider sign-ins that create an account (Decision 6), answering 429 `too_many_signups` with `Retry-After`. Verify in `tests/api/test_signup_limits.py`:
  - every scenario in the user-auth delta;
  - a refused request creates nothing and sends nothing;
  - a provider sign-in to an existing account succeeds at the limit;
  - an email-link to an existing account is not counted;
  - `X-Forwarded-For` behind `TRUSTED_PROXY_HOPS=1`;
  - existing registration and social sign-in tests still pass.

## 3. Referral cycle

- [ ] 3.1 Refuse a direct cycle in `ReferralService.redeem` inside the store transaction (Decision 4). Verify in `tests/services/test_referral_service.py` or the API tests:
  - A redeems B's code, then B redeeming A's code gets 409 `referral_not_allowed` with no credit change;
  - a third account C can still redeem A's code;
  - the existing redemption tests pass.

## 4. App messages

- [ ] 4.1 Add `disposable_email` and `too_many_signups` to `core/api_errors.dart`, with the messages and wait formatting from Decision 5, on the register screen, the change email screen and provider sign-in. Verify with widget tests:
  - each scenario in the account-ui delta;
  - 1800 seconds reads "30 minutes", 61 seconds reads "2 minutes", and 45 seconds reads "45 seconds";
  - fields are kept;
  - the existing `too_many_requests` "codes" message is unchanged.

## 5. Documentation

- [ ] 5.1 In `server/README.md`, document:
  - the disposable list (its source, how to edit it, and that changes apply at restart);
  - the per-address limits;
  - `TRUSTED_PROXY_HOPS`, with `1` behind one AWS ALB;
  - that counts are per process and in memory.

  Add both new settings to `.env.example`. In `todo.md`, remove "Referral farming" and "Mutual referral redemption", and add to the deployment checklist: "share the sign-up limiter (Redis or the database) before running several instances". Verify with `git diff`.

## 6. Integration and hand-off

- [ ] 6.1 Run `uv run pytest -q` in `server/` on Python 3.11, and `flutter analyze && flutter test` in `app/`. Verify:
  - all tests pass, with counts reported;
  - `openspec validate add-abuse-limits --strict` passes;
  - the md5 of `app.db` is unchanged.
- [ ] 6.2 **Manual.** Use a local server in log mode on a temporary storage root, with the iOS simulator and the Android emulator:
  - registering with a `mailinator.com` address shows "Use a permanent email address.";
  - a sixth registration in an hour from the same machine shows the network message with minutes;
  - changing email to a disposable address is refused;
  - with two provider test accounts, mutual redemption is refused, if the consoles are available.

  This box stays unticked until someone runs it. It is part of the user's combined manual pass.
- [ ] 6.3 Push `feat/add-abuse-limits`. Verify with `git ls-remote` that it matches the local HEAD.
