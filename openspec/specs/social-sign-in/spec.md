# social-sign-in Specification

## Purpose
Lets people sign in with an identity they already have at Google or Apple instead of a password. Covers checking provider tokens, finding, linking or creating the account, and confirming account deletion with a provider.

## Requirements

### Requirement: Sign in with Google

The system SHALL expose `POST /auth/oauth/google` taking an `id_token`. It SHALL accept the token only when Google's published keys verify its signature, its issuer is Google, its audience is one of the configured Google client IDs, and it has not expired. On success it SHALL respond with HTTP 200 and a body containing a session `token`, the user's `id` and `email`, and `created`, which is true only when the request created the account. A token that fails any check SHALL get HTTP 401 with error `invalid_provider_token`.

#### Scenario: Valid Google token signs in

- **WHEN** a client posts a valid Google ID token for an identity linked to an account
- **THEN** the system responds with HTTP 200, a `token` that authorizes `GET /me`, and `created` false

#### Scenario: Wrong audience is rejected

- **WHEN** a client posts a correctly signed Google token issued for a client ID that is not configured
- **THEN** the system responds with HTTP 401 and error `invalid_provider_token`

#### Scenario: Expired or forged token is rejected

- **WHEN** a client posts an expired Google token, or one whose signature does not verify
- **THEN** the system responds with HTTP 401 and error `invalid_provider_token`
- **AND** no account is created

### Requirement: Sign in with Apple

The system SHALL expose `POST /auth/oauth/apple` taking an `identity_token`, the raw `nonce` the app generated, and an `authorization_code`. It SHALL accept the identity token only when Apple's published keys verify its signature, its issuer is Apple, its audience is the configured app bundle ID, it has not expired, and its nonce claim equals the SHA-256 hex digest of the given `nonce`. On success it SHALL respond as for Google sign-in. A token that fails any check SHALL get HTTP 401 with error `invalid_provider_token`.

#### Scenario: Valid Apple token signs in

- **WHEN** a client posts a valid Apple identity token with the matching nonce for an identity linked to an account
- **THEN** the system responds with HTTP 200 and a session `token`

#### Scenario: Nonce mismatch is rejected

- **WHEN** a client posts a valid Apple identity token with a `nonce` whose digest does not match the token
- **THEN** the system responds with HTTP 401 and error `invalid_provider_token`

### Requirement: Find, link, or create the account

For an accepted provider token the system SHALL sign in to the account already linked to that provider identity. When no account is linked to it, but an account has the token's email (matched ignoring letter case), the system SHALL link the identity to that account and sign in to it. Otherwise it SHALL create a new account, but only when the request carries a `date_of_birth` that passes the age check described by the age-and-consent capability. A request that would create an account without a `date_of_birth` SHALL get HTTP 400 with error `age_required`. A request whose `date_of_birth` is under 18 SHALL get HTTP 400 with error `under_age`. In both cases no account SHALL be created and no Apple authorization code SHALL be exchanged. A `date_of_birth` sent with a sign-in to a linked or existing account SHALL be ignored. The account's email SHALL NOT change because the provider reports a different email for an identity that is already linked.

#### Scenario: Linked identity signs in to its account

- **WHEN** a Google identity is linked to an account and signs in again
- **THEN** the session belongs to that account and `created` is false

#### Scenario: Existing password account is linked by email

- **WHEN** an account registered with email and password exists for `ana@example.com` and a Google identity with that verified email signs in for the first time
- **THEN** the session belongs to the existing account and `created` is false
- **AND** `GET /me` lists `google` in `providers` and `has_password` is still true

#### Scenario: New identity with a new email creates an account

- **WHEN** a Google identity whose email has no account signs in
- **THEN** a new account is created with that email and `created` is true

#### Scenario: Changed provider email does not move the account

- **WHEN** a linked Google identity signs in with a token reporting a different email than the account's
- **THEN** the session belongs to the linked account and the account's email is unchanged

#### Scenario: Apple relay email is used as the account email

- **WHEN** a new Apple identity signs in with a private relay email address
- **THEN** a new account is created with that relay address as its email

#### Scenario: New account without a date of birth asks for one

- **WHEN** a Google identity whose email has no account signs in without a `date_of_birth`
- **THEN** the system responds with HTTP 400 and error `age_required`
- **AND** no account exists for that email

#### Scenario: Retrying with a date of birth creates the account

- **WHEN** the same Google token is sent again with a date of birth at least 18 years before today
- **THEN** a new account is created, `created` is true, and `GET /me` reports `age_confirmed` true

#### Scenario: Under-18 provider sign-up is refused

- **WHEN** a new Apple identity signs in with a date of birth under 18
- **THEN** the system responds with HTTP 400 and error `under_age`
- **AND** no account is created and the Apple authorization code is not exchanged

#### Scenario: Existing accounts are not asked

- **WHEN** a Google identity already linked to an account signs in without a `date_of_birth`
- **THEN** the sign-in succeeds with `created` false

### Requirement: Accounts created through a provider

An account created through a provider SHALL have no password and a referral code, and SHALL be able to submit generations straight away.

#### Scenario: New provider account can generate

- **WHEN** a new account is created through Google
- **THEN** `GET /me` reports `has_password` false
- **AND** the account can submit a generation

### Requirement: Require a provider-verified email

For a provider identity that is not linked to any account, the system SHALL NOT create or link an account unless the token's `email_verified` claim is true (the boolean `true` or the string `"true"`). This SHALL apply to Google and Apple alike. A missing or false claim SHALL get HTTP 400 with error `provider_email_unverified`. An Apple identity that is not linked to any account and whose token carries no email SHALL get HTTP 400 with error `provider_email_missing`.

#### Scenario: Unverified Google email is refused

- **WHEN** a Google token that is otherwise valid has `email_verified` false and no account is linked to that identity
- **THEN** the system responds with HTTP 400 and error `provider_email_unverified`
- **AND** no account is created or linked

#### Scenario: Apple email without a verified claim is refused

- **WHEN** an Apple token that is otherwise valid carries an email and its `email_verified` claim is missing, false, or the string `"false"`, and no account is linked to that identity
- **THEN** the system responds with HTTP 400 and error `provider_email_unverified`
- **AND** no account is created or linked

#### Scenario: Apple string claim is accepted

- **WHEN** a new Apple identity's token carries an email and `email_verified` set to the string `"true"`
- **THEN** an account is created

#### Scenario: Apple token without email for an unknown identity

- **WHEN** an Apple token without an email claim arrives for an identity that is not linked to any account
- **THEN** the system responds with HTTP 400 and error `provider_email_missing`

### Requirement: Refuse unconfigured providers

When the server has no client configuration for a provider, its sign-in endpoint SHALL respond with HTTP 503 and error `provider_not_configured`.

#### Scenario: Google is not configured

- **WHEN** no Google client IDs are configured and a client posts to `POST /auth/oauth/google`
- **THEN** the system responds with HTTP 503 and error `provider_not_configured`

### Requirement: Report an unreachable provider

When the system cannot obtain a provider's signing keys to check a token, it SHALL respond with HTTP 503 and error `provider_unavailable`, and SHALL NOT create, link, or delete anything.

#### Scenario: Google keys cannot be fetched

- **WHEN** Google's key endpoint does not respond and the server has no cached keys that match the token
- **THEN** the system responds with HTTP 503 and error `provider_unavailable`
- **AND** no account is created

### Requirement: One identity per provider per account

An account SHALL be linked to at most one identity of each provider. When linking by email would give an account a second identity of a provider it is already linked to, the system SHALL respond with HTTP 409 and error `provider_already_linked` and change nothing.

#### Scenario: Second Google identity for the same account is refused

- **WHEN** an account is linked to one Google identity and a different Google identity with the same email signs in
- **THEN** the system responds with HTTP 409 and error `provider_already_linked`

### Requirement: Confirm account deletion with a provider

`DELETE /me` SHALL accept a `provider` and a provider `token` as the confirmation. The token SHALL be accepted only when it passes the same checks as sign-in for that provider, belongs to the identity linked to the account for that provider, and was issued no more than 5 minutes earlier. Any other provider token SHALL get HTTP 403 with error `invalid_provider_token` and delete nothing.

#### Scenario: Fresh token from the linked identity deletes the account

- **WHEN** an authenticated user linked to Google calls `DELETE /me` with a Google token issued a minute ago for that identity
- **THEN** the system responds with HTTP 204

#### Scenario: Old token is refused

- **WHEN** the Google token was issued 10 minutes earlier
- **THEN** the system responds with HTTP 403 and error `invalid_provider_token` and the account remains usable

#### Scenario: Another person's token is refused

- **WHEN** the Google token is valid and fresh but belongs to a Google identity not linked to the account
- **THEN** the system responds with HTTP 403 and error `invalid_provider_token`

### Requirement: Revoke Apple authorization on account deletion

When an account linked to Apple is deleted and the server holds an Apple token for it, the system SHALL ask Apple to revoke that token. A failed revocation SHALL be logged and SHALL NOT stop the deletion.

#### Scenario: Apple token is revoked

- **WHEN** an account linked to Apple is deleted
- **THEN** the system sends Apple a revocation request for the account's stored Apple token

#### Scenario: Revocation failure does not block deletion

- **WHEN** Apple's revocation endpoint fails during an account deletion
- **THEN** the system responds with HTTP 204, the account is deleted, and the failure is logged

### Requirement: Keep provider tokens secret

The system SHALL NOT write provider ID tokens, authorization codes, or stored Apple tokens to the log, and SHALL NOT return them in any API response.

#### Scenario: Tokens are not logged

- **WHEN** a client signs in with Apple, including one attempt with an invalid token
- **THEN** the server log contains none of the identity token, the authorization code, or the Apple token obtained from it
