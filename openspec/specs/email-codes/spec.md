# email-codes Specification

## Purpose
One-time codes sent by email that prove a user controls their address. Used to verify an account's email and to reset its password.

## Requirements

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

### Requirement: Expire codes

A code SHALL be accepted only within 15 minutes (configurable) of being issued.

#### Scenario: Expired code is rejected

- **WHEN** a correct code is submitted 16 minutes after it was issued
- **THEN** the code is rejected as expired

#### Scenario: Code within its lifetime is accepted

- **WHEN** a correct code is submitted 14 minutes after it was issued
- **THEN** the code is accepted

### Requirement: Limit wrong attempts per code

After 5 (configurable) wrong submissions against an email address's code for a purpose, the system SHALL invalidate that code. Any later submission for that email address and purpose, including the correct code, SHALL be rejected until a new code is issued.

#### Scenario: Sixth submission is refused even when correct

- **WHEN** 5 wrong codes are submitted for an email address's registration code
- **AND** then the correct code is submitted
- **THEN** the correct code is rejected as expired

#### Scenario: A new code resets the count

- **WHEN** 5 wrong codes were submitted and a new code is then issued
- **THEN** the new code is accepted when submitted correctly

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

### Requirement: Deliver codes by email

When an SMTP server is configured, the system SHALL send each code as a plain-text email to the address it was issued for, stating the code, what it is for, and how many minutes it is valid. When no SMTP server is configured, the system SHALL instead write the recipient, the purpose, and the code to the server log, and SHALL log a warning at startup that emails are not being delivered. A delivery failure SHALL be logged and SHALL NOT change the response of the request that issued the code.

#### Scenario: Configured SMTP sends an email

- **WHEN** SMTP is configured and a registration code is issued
- **THEN** one email is sent to that address containing the 6-digit code and its validity in minutes

#### Scenario: Without SMTP the code is logged

- **WHEN** no SMTP server is configured and a registration code is issued
- **THEN** the server log contains the recipient, the purpose, and the code
- **AND** the startup log contains a warning that emails are not delivered

#### Scenario: Delivery failure does not fail the request

- **WHEN** the SMTP server refuses the connection while a code is being sent
- **THEN** the request that issued the code still succeeds
- **AND** the failure is logged without the code

### Requirement: Keep codes secret

The system SHALL store only a hash of each code, SHALL NOT return a code in any API response, and, when SMTP is configured, SHALL NOT write a code to the log.

#### Scenario: Stored code is not readable

- **WHEN** a code has been issued
- **THEN** the stored record does not contain the code's digits as text

#### Scenario: Responses never contain the code

- **WHEN** a client registers, registers again, or requests a password reset
- **THEN** no response body or header contains the issued code
