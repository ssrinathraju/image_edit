## ADDED Requirements

### Requirement: Refuse disposable email addresses

`POST /auth/register` and `POST /me/email` SHALL refuse an address whose domain, or any parent domain of it, is on the server's disposable-domain list, with HTTP 400, error `disposable_email` and the detail "Use a permanent email address.". Nothing SHALL be stored and no code SHALL be sent. Matching SHALL ignore letter case. Sign-ins through Google or Apple SHALL NOT be checked against the list, so Apple's private relay addresses keep working. The list SHALL be loaded when the server starts, and the server SHALL fail to start if the configured list file is missing or unreadable.

#### Scenario: Disposable domain is refused at registration

- **WHEN** a client registers `someone@mailinator.com` with a valid password and date of birth
- **THEN** the response is HTTP 400 with error `disposable_email`
- **AND** no code is sent and no pending registration exists for that address

#### Scenario: Subdomain of a listed domain is refused

- **WHEN** a client registers an address at `mx.mailinator.com` while `mailinator.com` is listed
- **THEN** the response is HTTP 400 with error `disposable_email`

#### Scenario: Ordinary domain is accepted

- **WHEN** a client registers an address at a domain that is not on the list
- **THEN** registration proceeds as before

#### Scenario: Email change to a disposable address is refused

- **WHEN** a signed-in user requests an email change to an address at a listed domain
- **THEN** the response is HTTP 400 with error `disposable_email` and no code is sent

#### Scenario: Missing list file prevents startup

- **WHEN** the server starts and the configured disposable-domain file does not exist
- **THEN** the server fails to start and names the missing file

### Requirement: Limit new accounts per network address

The system SHALL count, per client network address, each accepted `POST /auth/register` and each provider sign-in that creates a new account. When an address has 5 counted requests in the last hour, or 10 in the last 24 hours, a further such request from it SHALL get HTTP 429 with error `too_many_signups` and a `Retry-After` header giving the seconds until it would be allowed, and SHALL NOT store anything, send a code, or create an account. Refused requests SHALL NOT be counted. Signing in to an existing account, logging in, and every other endpoint SHALL NOT be affected. The client address SHALL be the connection's address when `TRUSTED_PROXY_HOPS` is 0 (the default); when it is N, it SHALL be the address N hops from the right of `X-Forwarded-For`, falling back to the connection's address when the header has fewer entries.

#### Scenario: Sixth registration in an hour is refused

- **WHEN** five registrations from one address have been accepted in the last hour and a sixth is posted
- **THEN** the response is HTTP 429 with error `too_many_signups` and a `Retry-After` header
- **AND** no code is sent

#### Scenario: Daily limit

- **WHEN** ten registrations from one address were accepted in the last 24 hours, spread so that fewer than five fall in the last hour
- **THEN** the next registration from that address gets HTTP 429 with error `too_many_signups`

#### Scenario: Other addresses are unaffected

- **WHEN** one address has reached the limit and another address registers
- **THEN** the other address's registration is accepted

#### Scenario: Provider sign-in to an existing account is not limited

- **WHEN** an address has reached the limit and a user signs in with Google to an account that already exists
- **THEN** the sign-in succeeds

#### Scenario: Provider sign-up counts toward the limit

- **WHEN** an address has reached the limit and a Google sign-in from it would create a new account
- **THEN** the response is HTTP 429 with error `too_many_signups` and no account is created

#### Scenario: Forwarded address behind one proxy

- **WHEN** `TRUSTED_PROXY_HOPS` is 1 and requests arrive from the proxy with `X-Forwarded-For: <spoofed>, <client>`
- **THEN** the limit is counted for `<client>`, not for the spoofed address or the proxy

#### Scenario: Window passes

- **WHEN** an address was refused with `Retry-After: 600` and registers again more than 600 seconds later
- **THEN** the registration is accepted
