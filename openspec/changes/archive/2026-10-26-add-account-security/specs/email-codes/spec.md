## MODIFIED Requirements

### Requirement: Issue one-time codes per email address and purpose

The system SHALL issue codes of exactly 6 decimal digits, chosen at random, each for one email address and one purpose: registration, password reset, or email change. Issuing a code SHALL invalidate any earlier code of the same email address and purpose. A code SHALL be accepted at most once.

#### Scenario: A new code replaces the old one

- **WHEN** an email address is issued a registration code and then a second registration code
- **THEN** the first code is rejected
- **AND** the second code is accepted

#### Scenario: Purposes are independent

- **WHEN** an email address holds both a registration code and a password reset code
- **THEN** each code is accepted only for its own purpose

#### Scenario: A used code cannot be reused

- **WHEN** a code has been accepted once
- **THEN** submitting the same code again is rejected

#### Scenario: Email-change codes are separate

- **WHEN** an address holds a registration code and an email-change code
- **THEN** the email-change code is accepted only to confirm an email change

### Requirement: Limit how often codes are emailed

The system SHALL NOT email a code to an email address within 60 seconds (configurable) of the previous code email to that address, and SHALL NOT send more than 5 (configurable) code emails to one address in any 60-minute window, counting all purposes together. When a limit applies, no new code SHALL be issued and the existing code SHALL stay valid.

#### Scenario: A second email within a minute is not sent

- **WHEN** a code is emailed to an address and another is requested 30 seconds later
- **THEN** no second email is sent
- **AND** the first code is still accepted

#### Scenario: Hourly cap counts both purposes

- **WHEN** an address has been sent 3 registration emails and 2 password reset emails in the last hour, each more than 60 seconds apart
- **AND** another code of either purpose is requested
- **THEN** no email is sent

#### Scenario: Cap frees up after an hour

- **WHEN** 61 minutes have passed since the oldest of 5 code emails to an address
- **THEN** a new code can be emailed to that address

#### Scenario: Email-change codes count toward the cap

- **WHEN** an address has been sent 4 registration emails and 1 email-change email in the last hour, each more than 60 seconds apart
- **AND** another code of any purpose is requested for it
- **THEN** no email is sent

