# Design

## Context

The server stores one Apple token per account in `identities.apple_refresh_token`. Three places touch it:
- **Stored:** `AuthService.store_apple_refresh_token` saves it once, after exchanging an Apple authorization code (it skips the exchange when a token is already held).
- **Read:** `get_apple_refresh_token` reads it at account deletion. `unlink_identity` (in `user_store_security.py`) reads it and returns it when Apple is unlinked, and the caller then schedules the revocation.
- **Revoked:** revocation runs in the background, and a failure is logged without blocking anything.

Apple counts as "configured" when the `APPLE_TEAM_ID`, `APPLE_KEY_ID` and `APPLE_PRIVATE_KEY_PATH` settings are set, and `Settings._check_apple_key_settings` already validates them together. `cryptography` 50.0.2 is already locked as a dependency of `pyjwt[crypto]`.

## Decisions

### Decision 1: AES-256-GCM with the account id as associated data
`core/token_cipher.py` holds a `TokenCipher` built from the 32-byte key, with two methods:
- **`encrypt(token, account_id) -> str`:** generates a fresh 12-byte nonce (`os.urandom`) and returns `"v1:" + base64url(nonce + AESGCM.encrypt(nonce, token, account_id))`.
- **`decrypt(value, account_id) -> Optional[str]`:** returns `None` when the value has no `v1:` prefix, when base64 decoding fails, when it is too short, or when `AESGCM.decrypt` raises `InvalidTag`. It never raises for bad input.

Passing the account id as associated data ties each ciphertext to its row. GCM also detects tampering.

**Rejected:** Fernet. It uses AES-128-CBC with HMAC and has no associated data, so a value copied between rows would still decrypt.

**Rejected:** AWS KMS per token. That means a network call on every use, AWS-only code, and harder local development. It is more than this rarely-read token needs.

### Decision 2: Encrypt in the repository layer
`SqliteUserStore` takes an optional `TokenCipher`. `set_apple_refresh_token` encrypts before writing. `get_apple_refresh_token` and `unlink_identity` decrypt before returning. The services and the store protocol keep handling plain tokens, so callers don't change.

If decryption returns `None`, the store logs `apple_token_unreadable user=<id>` at WARNING and returns `None`. Every caller already treats `None` as "no token held", which gives the "continue without revocation" behaviour with no changes to the services.

With no cipher (Apple not configured), `set_apple_refresh_token` refuses with a clear error. That can't happen in normal use, because the code exchange only runs when Apple is configured.

**Rejected:** encrypting in the services. There are three call sites, and a storage concern would leak into the business logic.

### Decision 3: The key setting and the startup rule
`TOKEN_ENCRYPTION_KEY: str = ""` is checked in a `Settings` validator:
- If it's set, it must base64-decode (standard or URL-safe) to exactly 32 bytes; otherwise startup fails naming the setting.
- If the Apple key settings are set and the key is empty, startup also fails naming the setting.

`create_app` builds the `TokenCipher` when the key is set and passes it to the store. The key is never logged.

**Rejected:** requiring the key always. Every local run and test would need a key, for no protection when Apple is off. The user chose the conditional rule.

### Decision 4: Delete plain-text tokens at startup (the user's choice)
When the store opens, after migration, it runs a single `UPDATE identities SET apple_refresh_token = NULL WHERE apple_refresh_token IS NOT NULL AND apple_refresh_token NOT LIKE 'v1:%'` in a transaction. It logs `apple_tokens_discarded count=<n>` when n > 0. This runs whether or not a key is set, so plain text never survives an upgrade.

**Rejected:** encrypting the existing tokens. The user chose to delete them. Before launch only development accounts hold any.

Accepted cost: those accounts can't have their Apple authorization revoked at deletion until a later Apple sign-in stores a fresh token.

### Decision 5: Self-healing after a key loss
`store_apple_refresh_token` skips the code exchange only when `get_apple_refresh_token` returns a token. An unreadable token reads as `None`, so the next Apple sign-in that carries an authorization code exchanges it and overwrites the row with a token encrypted under the current key. This needs no extra code; a test pins it.

### Decision 6: A version prefix, no rotation yet
The `v1:` prefix leaves room for a future `v2` key, but there is only one key today (CLAUDE.md §3).

## Risks and trade-offs

- **Data stored:** encrypted Apple tokens, kept for as long as the identity exists, as before. The key lives only in the environment or in memory.
- **Who can read it:** only a process that has both the database and the key. A database copy on its own reveals nothing.
- **Logging:** account ids and counts only. The key, tokens and ciphertexts are never logged, and the existing "tokens are not logged" requirement still applies.
- **Migration:** a one-time delete of plain-text tokens. Identities and Apple sign-in are unaffected.
- **Losing the key:** stored tokens become unreadable. Deletions and unlinks still complete without revocation (with a warning), and the next Apple sign-in with a code stores a fresh token.
- **Failure and retry:** a decrypt failure is not retried, because nothing can fix it except the right key. Revocation failures are handled as today.
- **Background tasks:** revocation still runs in the background. It receives the decrypted token or `None`.
- **Thread-safety:** `AESGCM` objects are safe to share for encryption with a fresh nonce on every call, and the store's lock is unchanged. 12-byte random nonces are safe at this volume, far below the birthday bound for collisions.
