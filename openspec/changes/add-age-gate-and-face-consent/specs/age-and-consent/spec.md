## Purpose

Makes sure only adults use the service and that each account has agreed to how face photos are handled before any are uploaded. Covers the age check, recording and withdrawing consent, and reporting both on the account.

## ADDED Requirements

### Requirement: Check a date of birth

Wherever the system takes a `date_of_birth`, it SHALL accept only a calendar date written as `YYYY-MM-DD` that is not after today's date in UTC. Otherwise it SHALL respond with HTTP 400 and error `invalid_date_of_birth`. A person SHALL count as 18 or older from the same month and day 18 years after their birth. A 29 February birth date SHALL count from 1 March in years without a 29 February. A date that is valid but under 18 SHALL get error `under_age`.

#### Scenario: Exactly 18 today is accepted

- **WHEN** a date of birth falls on today's month and day 18 years ago
- **THEN** it passes the age check

#### Scenario: One day short of 18 is refused

- **WHEN** a date of birth is one day less than 18 years before today
- **THEN** the system answers with error `under_age`

#### Scenario: Leap-day birth

- **WHEN** a person born on 29 February 2008 is checked on 28 February 2026
- **THEN** the system answers with error `under_age`
- **AND** the same date passes the check on 1 March 2026

#### Scenario: Malformed or future date

- **WHEN** a date of birth is `2008-13-01`, `08/05/2001`, or tomorrow's date
- **THEN** the system responds with HTTP 400 and error `invalid_date_of_birth`

### Requirement: Never store the date of birth

The system SHALL NOT store, log, or return a submitted date of birth. It SHALL store only whether the account's age was confirmed and when.

#### Scenario: Only the confirmation is kept

- **WHEN** an account is created with a date of birth
- **THEN** the stored account record and the server log contain no date of birth
- **AND** `GET /me` reports `age_confirmed` true and no date of birth

### Requirement: Confirm the age of an existing account

The system SHALL expose `POST /me/age`, for authenticated requests, taking a `date_of_birth`, for accounts whose age is not confirmed. An adult date SHALL mark the age confirmed and respond with HTTP 200. An under-18 date SHALL get HTTP 403 with error `under_age` and SHALL leave the account unchanged. An account whose age is already confirmed SHALL get HTTP 409 with error `age_already_confirmed`.

#### Scenario: Existing account confirms its age

- **WHEN** an account whose age is not confirmed posts an adult date of birth
- **THEN** the system responds with HTTP 200 and `GET /me` reports `age_confirmed` true

#### Scenario: Under-18 date leaves the account unconfirmed

- **WHEN** an account whose age is not confirmed posts a date of birth under 18
- **THEN** the system responds with HTTP 403 and error `under_age`
- **AND** `GET /me` still reports `age_confirmed` false

#### Scenario: Already confirmed

- **WHEN** an account whose age is confirmed posts any date of birth
- **THEN** the system responds with HTTP 409 and error `age_already_confirmed`

### Requirement: Treat existing accounts as unconfirmed

Accounts that existed before this capability SHALL have neither a confirmed age nor any consent when the server first starts afterwards.

#### Scenario: Existing account after the upgrade

- **WHEN** the server starts on a database holding an account created before this capability
- **THEN** `GET /me` for that account reports `age_confirmed` false and no accepted consent version

### Requirement: Record face-photo consent

The system SHALL have a configured current consent version, `"1"` by default. It SHALL expose `POST /me/consent`, for authenticated requests, taking a `version`. When the version equals the current version, the system SHALL record that the account accepted it and when, and respond with HTTP 200. Any other version SHALL get HTTP 400 with error `consent_version_mismatch` and record nothing.

#### Scenario: Current version is accepted

- **WHEN** an account posts the current consent version
- **THEN** the system responds with HTTP 200 and `GET /me` reports that version as accepted with the acceptance time

#### Scenario: Outdated version is refused

- **WHEN** the current version is "2" and an account posts version "1"
- **THEN** the system responds with HTTP 400 and error `consent_version_mismatch`
- **AND** nothing is recorded

### Requirement: Withdraw face-photo consent

The system SHALL expose `DELETE /me/consent`, for authenticated requests, which removes the account's recorded consent and responds with HTTP 204, whether or not consent had been given.

#### Scenario: Withdrawal removes consent

- **WHEN** an account that accepted the current version calls `DELETE /me/consent`
- **THEN** the system responds with HTTP 204 and `GET /me` reports no accepted version

### Requirement: Report age and consent on the account

`GET /me` SHALL include `age_confirmed` (boolean) and `consent`, an object holding `accepted_version` (or null), `accepted_at` (or null), and `current_version`.

#### Scenario: Fields for a new account

- **WHEN** an account created with an adult date of birth and without consent calls `GET /me`
- **THEN** the response contains `age_confirmed` true and `consent` with `accepted_version` null and `current_version` "1"
