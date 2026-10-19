## MODIFIED Requirements

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

