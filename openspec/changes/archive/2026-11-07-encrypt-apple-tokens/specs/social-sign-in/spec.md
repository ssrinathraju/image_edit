## ADDED Requirements

### Requirement: Store Apple tokens only in encrypted form

The system SHALL store each Apple token it keeps for an account only in encrypted form, using a server-held key from the `TOKEN_ENCRYPTION_KEY` setting, so the stored value reveals nothing about the token without the key. The encryption SHALL be bound to the account, so an encrypted value copied onto another account's row SHALL NOT decrypt. When Apple sign-in is configured (the Apple key settings are set), the server SHALL refuse to start without a valid `TOKEN_ENCRYPTION_KEY` and SHALL name the setting. A `TOKEN_ENCRYPTION_KEY` that is set but is not a base64 encoding of exactly 32 bytes SHALL also stop startup. The key SHALL NOT be logged.

#### Scenario: Stored value does not contain the token

- **WHEN** a user signs in with Apple for the first time and the server stores the Apple token
- **THEN** the value saved in the database does not contain the token text
- **AND** deleting that account sends Apple a revocation request carrying the original token

#### Scenario: Value copied to another account is useless

- **WHEN** the encrypted value stored for account A is copied onto account B's Apple identity and account B is deleted
- **THEN** no revocation request is sent for B, and B's deletion completes

#### Scenario: Apple configured without a key

- **WHEN** the server starts with the Apple key settings set and `TOKEN_ENCRYPTION_KEY` empty
- **THEN** startup fails with a message naming `TOKEN_ENCRYPTION_KEY`

#### Scenario: Malformed key

- **WHEN** the server starts with a `TOKEN_ENCRYPTION_KEY` that does not decode to 32 bytes
- **THEN** startup fails with a message naming `TOKEN_ENCRYPTION_KEY`

#### Scenario: No Apple, no key

- **WHEN** the server starts without the Apple key settings and without `TOKEN_ENCRYPTION_KEY`
- **THEN** it starts normally

### Requirement: Discard Apple tokens stored before encryption

At startup the system SHALL remove every stored Apple token that is not in the encrypted form, leaving the Apple identity linked. It SHALL log only how many it removed. An account whose token was removed SHALL behave as an account for which the server holds no Apple token.

#### Scenario: Plain-text token is removed at startup

- **WHEN** the database holds a plain-text Apple token from before this change and the server starts
- **THEN** that token is no longer stored, the account is still linked to Apple and can sign in with Apple
- **AND** the log records the number of tokens removed and none of their values

#### Scenario: Deleting an account whose old token was removed

- **WHEN** an account whose plain-text token was removed is deleted
- **THEN** no revocation request is sent and the deletion completes with HTTP 204

### Requirement: Continue when a stored Apple token cannot be decrypted

When the system needs a stored Apple token to revoke it, during account deletion or Apple unlink, and the token cannot be decrypted (a different key, or a damaged value), it SHALL send no revocation request, SHALL log a warning naming only the account id, and SHALL complete the deletion or unlink as if no token were held.

#### Scenario: Key changed before deletion

- **WHEN** an Apple token was stored under one key, the server restarts with a different `TOKEN_ENCRYPTION_KEY`, and the account is deleted
- **THEN** the deletion completes with HTTP 204, no revocation request is sent, and a warning with the account id is logged

#### Scenario: Damaged value on unlink

- **WHEN** the stored encrypted value for an account has been altered and the user unlinks Apple
- **THEN** the unlink completes, no revocation request is sent, and a warning with the account id is logged
