# Proposal

## Why

Signing up with an email and password, then typing a code, is the slowest path into the app. Most people already have a Google account, and every iPhone user has an Apple ID. One-tap sign-in removes most of that friction. App Store rules also apply: an iOS app that offers Google sign-in must offer Sign in with Apple, and it must revoke Apple's authorization when an account is deleted. This was split out of `add-email-verification-and-reset` and comes next.

## What Changes

- New endpoints:
  - `POST /auth/oauth/google` checks a Google ID token.
  - `POST /auth/oauth/apple` checks an Apple identity token, its nonce and an authorization code.

  Each one signs in to the linked account, links the identity to an existing account with the same email (the provider has verified it), or creates a new account. Responses carry the usual session plus `created`.
- Accounts created through a provider have a verified email and **no password**. Password login on them fails like a wrong password. A password reset gives them a password.
- Each account can have at most one identity per provider. If a provider is not configured its endpoint answers 503. If its keys are unreachable it answers 503 `provider_unavailable`.
- `DELETE /me` accepts either the password or a fresh provider sign-in token (issued within 5 minutes) as confirmation. Deleting an Apple-linked account asks Apple to revoke its token, and a failed revocation is logged without blocking the deletion.
- New `POST /me/referral`: an account created through a provider can redeem a referral code once, within 24 hours of creation, with the usual rewards and cap.
- `GET /me` adds `providers` and `has_password`.
- New server dependency: `pyjwt[crypto]`. New settings: `GOOGLE_CLIENT_IDS` and `APPLE_BUNDLE_ID`, plus `APPLE_TEAM_ID`, `APPLE_KEY_ID` and `APPLE_PRIVATE_KEY_PATH` for revocation.
- App:
  - **Sign-in and registration screens:** "Continue with Google" on iOS and Android, and "Continue with Apple" on iOS. A button is hidden when its provider is not configured, and cancelling the provider sheet is silent.
  - **New account through a provider:** a skippable "Have a referral code?" screen before home.
  - **Profile:** shows the linked providers.
  - **Delete account:** asks for the password, or for a provider sign-in when the account has no password.

Out of scope:
- Apple sign-in on Android (it needs a hosted HTTPS redirect).
- Linking or unlinking providers from the profile.
- Other providers.
- Setting a password while signed in (password reset covers it).
- Web.
- Creating the Google Cloud and Apple Developer configuration, which the user does outside the repo.

## Capabilities

### New Capabilities
- `social-sign-in`: covers signing in with Google and Apple. It owns checking provider tokens, finding, linking or creating the account, the verified-email rules for provider accounts, unconfigured and unreachable providers, confirming deletion with a provider, revoking Apple's authorization, and keeping tokens secret.

### Modified Capabilities
- `user-auth`:
  - "Delete an account" accepts a provider confirmation and removes linked providers.
  - New requirements for accounts without a password and for reporting sign-in methods on `/me`.
- `referrals`: a new requirement for redeeming a code after a provider sign-up.
- `account-ui`:
  - "Delete the account" asks for the password or a provider sign-in.
  - New requirements for the provider buttons, the referral prompt and the profile's provider line.

## Impact

- **Server:**
  - `configs/settings.py`.
  - New `core/identity_verifier.py`, with Google and Apple verifiers under `services/identity/`.
  - New `services/apple_revocation.py`.
  - `repos/user_store.py`: schema version 4, an `identities` table, and new `created_via` and `referral_redeemed` columns.
  - `services/auth_service.py`, `services/referral_service.py`, `api/auth.py`, `schemas/user.py` and `main.py`.
  - `server/README.md`.
- **API:**
  - Three new endpoints.
  - `DELETE /me` takes a new request shape (the password form is unchanged).
  - Two new `/me` fields.
  - New error codes: `invalid_provider_token`, `provider_email_unverified`, `provider_email_missing`, `provider_not_configured`, `provider_unavailable`, `provider_already_linked` and `referral_not_allowed`.
- **Data:** `app.db` is migrated in place. Existing accounts become `created_via = password` with no identities.
- **App:**
  - New packages `google_sign_in`, `sign_in_with_apple` and `crypto`.
  - iOS native setup: a URL scheme and the Sign in with Apple entitlement.
  - Code: `configs/app_config.dart`, `core/api_client.dart`, `core/api_errors.dart`, `router.dart`, and screens under `features/auth/` and `features/profile/`.
  - New `.env` keys.
- **Outside the repo (the user's job, needed only for the manual pass and release):**
  - a Google Cloud OAuth client for iOS, for Android (package name and signing SHA-1) and for the web/server;
  - an Apple Developer Program membership, an App ID with Sign in with Apple, and a `.p8` key;
  - final bundle ID and package name.
