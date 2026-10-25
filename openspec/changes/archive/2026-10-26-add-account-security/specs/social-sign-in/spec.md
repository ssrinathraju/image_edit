## MODIFIED Requirements

### Requirement: Confirm account deletion with a provider

`DELETE /me` SHALL accept a `provider` and a provider `token` as the confirmation only for an account without a password. An account with a password SHALL confirm with its password, and a provider confirmation from it SHALL get HTTP 403 with error `invalid_provider_token`, deleting nothing. The token SHALL be accepted only when it passes the same checks as sign-in for that provider, belongs to the identity linked to the account for that provider, and was issued no more than 5 minutes earlier. Any other provider token SHALL get HTTP 403 with error `invalid_provider_token` and delete nothing.

#### Scenario: Fresh token from the linked identity deletes the account

- **WHEN** an authenticated user linked to Google calls `DELETE /me` with a Google token issued a minute ago for that identity
- **THEN** the system responds with HTTP 204

#### Scenario: Old token is refused

- **WHEN** the Google token was issued 10 minutes earlier
- **THEN** the system responds with HTTP 403 and error `invalid_provider_token` and the account remains usable

#### Scenario: Another person's token is refused

- **WHEN** the Google token is valid and fresh but belongs to a Google identity not linked to the account
- **THEN** the system responds with HTTP 403 and error `invalid_provider_token`

#### Scenario: Password account cannot delete with a provider token

- **WHEN** an account with a password and a linked Google identity calls `DELETE /me` with a fresh Google token for that identity
- **THEN** the system responds with HTTP 403 and error `invalid_provider_token` and the account remains usable

