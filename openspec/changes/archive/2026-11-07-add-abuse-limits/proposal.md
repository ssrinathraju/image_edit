# Proposal

## Why

Each new account gets free daily generations, and referrals add bonus credits, so throwaway accounts are worth farming. Today:
- disposable email addresses pass registration, because the code arrives in a public inbox;
- nothing limits how many accounts one machine creates;
- two new provider accounts can redeem each other's referral codes, each getting +5.

`todo.md` lists all three as needed before a public launch.

## What Changes

- **Disposable emails refused:** `POST /auth/register` and `POST /me/email` refuse addresses at a listed disposable domain, or a subdomain of one, with 400 `disposable_email`.
  - The list is a text file in `server/seed/abuse/disposable_domains.txt`, with one domain per line, from a public-domain source. It is loaded at startup, and its path is configurable.
  - Google and Apple sign-ins are not checked, so Apple private-relay addresses keep working.
- **Per-address sign-up limit:** at most **5 per hour and 10 per 24 hours** from one network address. This counts accepted registrations and provider sign-ins that create an account. Beyond the limit, the request gets 429 `too_many_signups` with `Retry-After`.
  - The client address comes from the connection, or from `X-Forwarded-For` counted `TRUSTED_PROXY_HOPS` hops from the right (default 0), so it can't be spoofed behind a known proxy.
  - Counts are held in memory only.
- **No mutual referrals:** `POST /me/referral` refuses a code whose owner was referred by the redeeming account, with 409 `referral_not_allowed`.
- **App:** clear messages for `disposable_email` and `too_many_signups` on registration, change email and provider sign-in.
- **todo.md:** remove the "Referral farming" and "Mutual referral redemption" items.

Out of scope:
- per-address limits on login, password reset, or generation;
- CAPTCHA;
- device fingerprinting;
- updating the disposable list automatically;
- limits shared across several server instances;
- reviewing existing accounts that used disposable addresses.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `user-auth`: the disposable-email refusal and the per-address limit on new accounts.
- `referrals`: a direct referral cycle is refused.
- `account-ui`: messages for the two new refusals.

## Impact

- **Server:**
  - new: `core/disposable_domains.py` (loading and matching), `core/signup_limiter.py` (the in-memory sliding window), `core/client_address.py` (resolving the client address), and `seed/abuse/disposable_domains.txt`;
  - changes to `auth_service.py` (register and provider sign-up), `account_security_service.py` (email change) and `referral_service.py` (the cycle rule);
  - wiring in `api/auth.py` (the client address) and `main.py`;
  - the settings `DISPOSABLE_DOMAINS_FILE` and `TRUSTED_PROXY_HOPS`;
  - `server/README.md` and `.env.example`.
- **App:** `core/api_errors.dart` (two codes), the register screen, the change email screen, and the provider sign-in error handling, with tests.
- **Existing data:** no migration. Existing accounts are untouched.
