# account-security Specification

## Purpose
Lets a signed-in user manage how they sign in: set or change their password, change their email address, and link or unlink Google and Apple. Every change requires proving it's really them, and other devices are signed out where it matters.

## Requirements

### Requirement: Confirm identity before a sensitive change

Every request in this capability, including linking a provider, SHALL carry a re-authentication. The form depends on the account:
- **An account with a password** SHALL give its current `password`, and SHALL NOT be accepted with a provider token.
- **An account without a password** SHALL give a `provider` and a fresh provider `token` (issued within the last 5 minutes) for an identity that was already linked to it before the request, checked as for account deletion.

An identity linked by the same request SHALL never count as re-authentication. A wrong password, a provider token from a password account, or a rejected token SHALL get HTTP 403 with error `reauth_failed`, and nothing SHALL change. Wrong passwords SHALL count toward the existing failed-login lockout for the account's email.

#### Scenario: Password account cannot re-authenticate with a provider

- **WHEN** an account with a password and a linked Google identity asks to change its password, giving a fresh Google token instead of its password
- **THEN** the system responds with HTTP 403 and error `reauth_failed`
- **AND** the password is unchanged

#### Scenario: A stolen session cannot take over the account

- **WHEN** a client holding only a password account's session links its own Google identity without the password
- **THEN** the link is refused with HTTP 403 and error `reauth_failed`
- **AND** the account's password and email cannot be changed with that Google identity

#### Scenario: Wrong current password changes nothing

- **WHEN** an account with a password asks to change its email and gives a wrong current password
- **THEN** the system responds with HTTP 403 and error `reauth_failed`
- **AND** no code is sent and nothing changes

#### Scenario: Provider-only account re-authenticates with its provider

- **WHEN** an account without a password asks to set a password and gives a Google token issued a minute ago for its linked identity
- **THEN** the request proceeds

#### Scenario: Old provider token is refused

- **WHEN** an account without a password gives a Google token issued 10 minutes ago
- **THEN** the system responds with HTTP 403 and error `reauth_failed`

#### Scenario: Repeated wrong passwords lock out

- **WHEN** 5 requests in a row give a wrong current password
- **THEN** the next request, even with the right password, gets HTTP 429 and error `too_many_attempts`

### Requirement: Set or change the password

The system SHALL expose `POST /me/password` with a `new_password` of 8 to 128 characters and a re-authentication. On success it SHALL set the new password and revoke every other session of the account, keeping the session used for the request. It SHALL email the account's address that the password was changed, and respond with HTTP 204. A new password outside the length limits SHALL get HTTP 400 with error `invalid_credentials_format`, and nothing SHALL change. An account without a password SHALL be able to set one this way.

#### Scenario: Change keeps this device and signs out others

- **WHEN** a user signed in on two devices changes the password from the first
- **THEN** the system responds with HTTP 204
- **AND** the first device's session still works, the second device's gets HTTP 401, and logging in with the new password succeeds

#### Scenario: Provider-only account sets a password

- **WHEN** an account created through Google sets a password with a fresh Google token
- **THEN** `GET /me` reports `has_password` true and logging in with the email and new password succeeds

#### Scenario: Notification goes to the account's address

- **WHEN** the password is changed
- **THEN** an email saying the password was changed is sent to the account's address, and it contains no code or password

### Requirement: Request an email change

The system SHALL expose `POST /me/email` with a `new_email` and a re-authentication. The new email SHALL be a valid address different from the current one, and SHALL NOT belong to another account; otherwise the system SHALL respond with HTTP 400 `invalid_credentials_format`, or HTTP 409 `email_taken`. When it passes, the system SHALL email an email-change code to the new address, remember the pending change for the account (replacing any earlier one), and respond with HTTP 202. The account's email SHALL NOT change yet. Sending limits SHALL apply as for other codes, and a limited request SHALL get HTTP 429 `too_many_requests` with `Retry-After`.

#### Scenario: Code goes to the new address

- **WHEN** a user asks to change their email to `new@example.com` with the right password
- **THEN** the system responds with HTTP 202 and an email-change code is sent to `new@example.com`
- **AND** `GET /me` still reports the old email

#### Scenario: Address used by another account

- **WHEN** the new email belongs to another account
- **THEN** the system responds with HTTP 409 and error `email_taken` and no code is sent

### Requirement: Confirm an email change with the code

The system SHALL expose `POST /me/email/confirm` with a `code`. When the code matches the account's pending email change, the system SHALL do the following in one step:
- change the account's email to the new address;
- clear the pending change;
- revoke every other session of the account, keeping the session used for the request;
- email the OLD address that the email was changed to the new one;
- respond with HTTP 200 and the new email.

A wrong code SHALL get HTTP 400 `invalid_code`. An expired or missing code SHALL get HTTP 400 `code_expired`. If the new address has meanwhile been taken by another account, the system SHALL respond with HTTP 409 `email_taken` and discard the pending change.

#### Scenario: Confirmed change

- **WHEN** a user confirms with the code sent to `new@example.com`
- **THEN** `GET /me` reports `new@example.com`
- **AND** logging in with `new@example.com` and the password succeeds, and with the old email returns 401
- **AND** other sessions get HTTP 401
- **AND** an email about the change is sent to the old address

#### Scenario: Wrong code

- **WHEN** a user confirms with a wrong code
- **THEN** the system responds with HTTP 400 and error `invalid_code` and the email is unchanged

#### Scenario: New address taken meanwhile

- **WHEN** another account registers `new@example.com` between the request and the confirmation
- **THEN** the confirmation gets HTTP 409 and error `email_taken` and the email is unchanged

### Requirement: Link a provider to the signed-in account

The system SHALL expose `POST /me/providers/google`, with an `id_token`, and `POST /me/providers/apple`, with an `identity_token`, a `nonce` and an `authorization_code`. Each SHALL be checked as for sign-in and SHALL link that identity to the signed-in account, responding with HTTP 200. The provider's email does not need to match the account's email, and the account's email SHALL NOT change. An identity already linked to another account SHALL get HTTP 409 `provider_in_use`. An account that already has that provider SHALL get HTTP 409 `provider_already_linked`. An invalid token SHALL get HTTP 401 `invalid_provider_token`. Each request SHALL also carry a re-authentication, as described in "Confirm identity before a sensitive change": the current password, or a fresh token from a provider already linked to the account. It SHALL be checked before anything is linked. The new identity's own token SHALL NOT serve as re-authentication.

#### Scenario: Link Google

- **WHEN** a password account links a Google identity that is not linked anywhere, giving its current password
- **THEN** the system responds with HTTP 200 and `GET /me` lists `google`
- **AND** signing in with that Google identity later reaches this account

#### Scenario: Linking without re-authentication is refused

- **WHEN** a password account links a Google identity without its password, or with a wrong one
- **THEN** the system responds with HTTP 403 and error `reauth_failed` and nothing is linked

#### Scenario: Provider-only account links with its existing provider

- **WHEN** an account created through Google links Apple, giving a fresh token for its already-linked Google identity
- **THEN** the system responds with HTTP 200 and `GET /me` lists both providers

#### Scenario: The new identity cannot vouch for itself

- **WHEN** an account created through Google tries to link Apple, giving only the new Apple identity's token as re-authentication
- **THEN** the system responds with HTTP 403 and error `reauth_failed` and nothing is linked

#### Scenario: Identity used by another account

- **WHEN** the Google identity is already linked to a different account
- **THEN** the system responds with HTTP 409 and error `provider_in_use` and nothing changes

### Requirement: Unlink a provider

The system SHALL expose `DELETE /me/providers/{provider}` with a re-authentication. It SHALL remove that provider's identity from the account and respond with HTTP 204, but only when the account would still have another way to sign in: a password or another linked provider. Otherwise it SHALL respond with HTTP 409 `last_sign_in_method` and change nothing. An account without that provider SHALL get HTTP 404. Unlinking Apple SHALL ask Apple to revoke the stored Apple token, and a failed revocation SHALL be logged and SHALL NOT stop the unlink.

#### Scenario: Unlink with a password present

- **WHEN** an account with a password and Google linked unlinks Google with its password
- **THEN** the system responds with HTTP 204 and `GET /me` lists no providers
- **AND** signing in with that Google identity afterwards creates a new account rather than reaching this one

#### Scenario: Last sign-in method is kept

- **WHEN** an account with no password and only Apple linked asks to unlink Apple
- **THEN** the system responds with HTTP 409 and error `last_sign_in_method`

#### Scenario: Unlinking Apple revokes its token

- **WHEN** an account with a password unlinks Apple
- **THEN** a revocation request for the stored Apple token is sent, and the unlink succeeds even if that request fails

### Requirement: Keep security changes private

The system SHALL NOT log passwords, codes, tokens or the new email address. Notification emails SHALL contain no code, password or token, and SHALL say what to do if the reader did not make the change:
- the password-changed notice SHALL tell the reader to reset their password;
- the email-changed notice, sent to the old address, SHALL name the new address and tell the reader to contact support right away at the configured support address. It SHALL NOT suggest a password reset, which cannot reach the account after the email has changed.

The support address SHALL be a server setting, and the server SHALL refuse to start when SMTP is configured and the support address is empty.

#### Scenario: Email-changed notice points to support

- **WHEN** an email-change notification is sent to the old address with the support address set to `help@example.com`
- **THEN** it names the new address, contains no code, tells the reader to contact `help@example.com` right away if they did not make the change, and does not mention resetting the password

#### Scenario: Password-changed notice suggests a reset

- **WHEN** a password-changed notification is sent
- **THEN** it contains no code or password and tells the reader to reset their password if they did not make the change

#### Scenario: SMTP without a support address

- **WHEN** the server starts with SMTP configured and an empty support address
- **THEN** it refuses to start with an error naming the support address setting
