# Spec Delta

## MODIFIED Requirements

### Requirement: Register an account

The system SHALL accept `POST /auth/register` with an `email`, a `password`, and an optional `referral_code`, create the account, and respond with HTTP 201 and a body containing a session `token` and the user's `id` and `email`. Emails SHALL be matched case-insensitively and stored in lowercase. Passwords SHALL be between 8 and 128 characters. An unknown `referral_code` SHALL be rejected as described by the referrals capability.

#### Scenario: Valid registration creates an account and a session

- **WHEN** a client posts a new email and a 12-character password to `POST /auth/register`
- **THEN** the system responds with HTTP 201 and a body containing `token`, `id`, and `email`
- **AND** that token authorizes `GET /me`

#### Scenario: Duplicate email is rejected

- **WHEN** a client registers an email that already has an account, in any letter case
- **THEN** the system responds with HTTP 409 and error `email_taken`

#### Scenario: Invalid email or weak password is rejected

- **WHEN** a client registers with a malformed email or a password shorter than 8 characters
- **THEN** the system responds with HTTP 400 and error `invalid_credentials_format`
- **AND** no account is created

#### Scenario: Unknown referral code is rejected

- **WHEN** a client registers with a valid email and password and a referral code that matches no account
- **THEN** the system responds with HTTP 400 and error `invalid_referral_code`
- **AND** no account is created

### Requirement: Return the current user

The system SHALL expose `GET /me` which returns the authenticated user's `id`, `email`, and `created_at`, together with the account's plan, usage, and referral details, and SHALL NOT return any password material.

#### Scenario: Current user is returned

- **WHEN** an authenticated client calls `GET /me`
- **THEN** the system responds with HTTP 200 and the user's `id`, `email`, and `created_at`

#### Scenario: Plan, usage, and referral details are included

- **WHEN** an authenticated client calls `GET /me`
- **THEN** the response also contains the account's `plan`, its usage figures, and its referral code and progress
