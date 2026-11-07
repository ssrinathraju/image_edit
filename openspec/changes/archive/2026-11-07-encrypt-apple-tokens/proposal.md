# Proposal

## Why

`identities.apple_refresh_token` is stored as plain text in `app.db`. Anyone who gets a copy of the database file, such as from a leaked backup, a misconfigured S3 bucket or a stolen disk snapshot, can read every user's Apple token. Those tokens are what the server uses to revoke the app's Sign in with Apple authorization. `todo.md` lists encrypting them as a pre-launch item, and the S3 backups planned in the deployment checklist make it more pressing.

## What Changes

- **Encrypt at rest:** Apple tokens are stored only in encrypted form, AES-256-GCM, using a server key from a new `TOKEN_ENCRYPTION_KEY` setting (32 bytes, base64).
  - The account id is bound in, so a value copied onto another account's row doesn't decrypt.
  - Stored values carry a `v1:` version prefix, so key rotation can be added later without a migration.
- **The key is required only when Apple is configured.** If the Apple key settings are set, startup fails without a valid key. Local development and tests without Apple need no key.
- **Existing plain-text tokens are deleted at startup** (the user's choice). Identities stay linked and Apple sign-in still works. Those accounts simply have no token to revoke. The next Apple sign-in that brings an authorization code stores a fresh, encrypted one, as today.
- **An unreadable token never blocks deletion or unlink** (the user's choice). If a token can't be decrypted, because of a wrong key or a damaged value, no revocation is sent, a warning with the account id is logged, and the deletion or unlink completes.
- **Docs:** `server/README.md` and `.env.example` document the setting. On AWS the key comes from Secrets Manager or SSM Parameter Store, passed as an environment variable. Remove the `todo.md` item.

Out of scope:
- key rotation (a second key, with old tokens re-encrypted);
- AWS KMS envelope encryption;
- encrypting other columns. Session tokens are already stored as hashes, and email codes are short-lived hashes.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `social-sign-in`: three added requirements: tokens stored encrypted (with the startup rule for the key), plain-text tokens discarded at startup, and continuing when a token can't be decrypted.

## Impact

- **Server only:**
  - new `core/token_cipher.py`;
  - `repos/user_store_identities.py` and `repos/user_store_security.py` (encrypt on write, decrypt on read, startup discard);
  - `repos/user_store.py` (passes the cipher);
  - `configs/settings.py` (the setting and its check);
  - `main.py`;
  - `server/README.md` and `server/.env.example`;
  - tests.
- **Dependencies:** `cryptography` becomes a direct dependency. It is already installed and locked through `pyjwt[crypto]` (50.0.2), so nothing new is downloaded.
- **Existing data:** plain-text Apple tokens are deleted once. On this machine's `app.db`, that's whatever the development accounts hold.
- **App:** unchanged.
