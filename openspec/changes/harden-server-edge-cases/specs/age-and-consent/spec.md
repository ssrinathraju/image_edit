## MODIFIED Requirements

### Requirement: Check a date of birth

Wherever the system takes a `date_of_birth`, it SHALL accept only a calendar date written as `YYYY-MM-DD` that is not after today's date in UTC. Otherwise it SHALL respond with HTTP 400 and error `invalid_date_of_birth`. This SHALL apply to any JSON value sent as `date_of_birth`, including a number, a boolean, an object, a list, or `null` where a date is required, and to a string of any length. A person SHALL count as 18 or older from the same month and day 18 years after their birth. A 29 February birth date SHALL count from 1 March in years without a 29 February. A date that is valid but under 18 SHALL get error `under_age`.

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

#### Scenario: Non-string date of birth

- **WHEN** a client registers, signs up through a provider, or calls `POST /me/age` with `date_of_birth` set to `19900101`, `true`, `{}`, or `[]`
- **THEN** the system responds with HTTP 400 and error `invalid_date_of_birth`
- **AND** the response does not contain the value that was sent

#### Scenario: Very long date string

- **WHEN** a client sends a `date_of_birth` string of 200 characters
- **THEN** the system responds with HTTP 400 and error `invalid_date_of_birth`
- **AND** the response does not contain the value that was sent

