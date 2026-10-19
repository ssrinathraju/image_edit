## MODIFIED Requirements

### Requirement: Start a registration

The system SHALL accept `POST /auth/register` with an `email`, a `password`, a `date_of_birth`, and an optional `referral_code`. The `date_of_birth` SHALL be checked as described by the age-and-consent capability before anything else is stored or sent. It SHALL NOT create an account. It SHALL hold the registration as pending, email a registration code to that address as described by the email-codes capability, and respond with HTTP 202 and an empty body. Emails SHALL be matched case-insensitively and stored in lowercase. Passwords SHALL be between 8 and 128 characters. An unknown `referral_code` SHALL be rejected as described by the referrals capability. Registering the same email again SHALL replace the pending registration and its code. When a sending limit applies, the system SHALL respond with HTTP 429, error `too_many_requests`, and a `Retry-After` header, and keep the previous pending registration.

#### Scenario: Valid registration sends a code and creates no account

- **WHEN** a client posts a new email and a 12-character password to `POST /auth/register`
- **THEN** the system responds with HTTP 202 and no session
- **AND** a registration code is sent to that email
- **AND** logging in with that email and password returns 401

#### Scenario: Registering again replaces the pending registration

- **WHEN** a client registers an email, waits more than 60 seconds, and registers the same email with a different password
- **THEN** a new code is sent and the first code is rejected
- **AND** confirming with the new code creates the account with the second password

#### Scenario: Registering again too soon is refused

- **WHEN** a client registers the same email twice within 60 seconds
- **THEN** the second request gets HTTP 429, error `too_many_requests`, and a `Retry-After` header
- **AND** the first code is still accepted

#### Scenario: Duplicate email is rejected

- **WHEN** a client registers an email that already has an account, in any letter case
- **THEN** the system responds with HTTP 409 and error `email_taken`

#### Scenario: Invalid email or weak password is rejected

- **WHEN** a client registers with a malformed email or a password shorter than 8 characters
- **THEN** the system responds with HTTP 400 and error `invalid_credentials_format`
- **AND** no code is sent

#### Scenario: Unknown referral code is rejected

- **WHEN** a client registers with a valid email and password and a referral code that matches no account
- **THEN** the system responds with HTTP 400 and error `invalid_referral_code`
- **AND** no code is sent

#### Scenario: Under-18 registration is refused

- **WHEN** a client registers with a date of birth 17 years and 364 days before today
- **THEN** the system responds with HTTP 400 and error `under_age`
- **AND** no code is sent and no pending registration exists for that email

#### Scenario: Missing date of birth is refused

- **WHEN** a client registers without a `date_of_birth`
- **THEN** the system responds with an error and no code is sent

#### Scenario: Confirmed registration is age-confirmed

- **WHEN** a client registers with a date of birth exactly 18 years before today and confirms the emailed code
- **THEN** `GET /me` for the new account reports `age_confirmed` true

