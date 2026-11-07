# Tasks

Work on branch `feat/encrypt-apple-tokens`. Do not push to `main`. The work is in `server/` only, with `todo.md`. "Decision N" refers to `design.md`. Tests use temporary storage roots and a fake Apple client. Never use a real key: generate one in the tests. Record the md5 of `server/storage/app.db` before and after each full test run, and never open it.

## 1. Cipher and setting

- [x] 1.1 Add `cryptography` as a direct dependency in `pyproject.toml`. Lock it with `uv lock`, keeping the locked 50.0.2. Add `core/token_cipher.py` (Decision 1). Verify in `tests/core/test_token_cipher.py`:
  - a value round-trips;
  - the output starts with `v1:` and doesn't contain the token;
  - two encryptions of the same token differ;
  - each of these returns `None`: the wrong account id, the wrong key, one changed byte, a missing prefix, bad base64, a too-short value.
- [x] 1.2 Add `TOKEN_ENCRYPTION_KEY` with the validator from Decision 3. Document it in `server/.env.example`. Verify in `tests/configs/test_settings.py`:
  - Apple configured without the key fails, naming `TOKEN_ENCRYPTION_KEY`;
  - a key decoding to 31 or 33 bytes fails;
  - a non-base64 key fails;
  - a valid key passes, in standard and URL-safe base64;
  - no Apple and no key passes;
  - the key never appears in the error messages.

## 2. Store

- [x] 2.1 Pass the cipher into `SqliteUserStore` from `create_app`. Encrypt in `set_apple_refresh_token`. Decrypt in `get_apple_refresh_token` and `unlink_identity`, logging `apple_token_unreadable user=<id>` when that fails (Decision 2). Verify in the repo tests:
  - the raw column value starts with `v1:` and doesn't contain the token;
  - get returns the original token;
  - a value copied onto another account's row returns `None`, with the warning logged;
  - reading under a different key returns `None`;
  - `unlink_identity` returns the decrypted token, or `None` for a damaged value;
  - without a cipher, `set_apple_refresh_token` refuses.
- [x] 2.2 Add the startup discard (Decision 4). Verify:
  - a store opened over a database holding plain-text tokens clears them and keeps those identities linked;
  - `v1:` values are kept;
  - the count is logged, and no value is logged (`caplog`);
  - it runs with and without a key.

## 3. Flows

- [x] 3.1 Verify the end-to-end behaviour with API tests using the fake Apple client:
  - an Apple sign-in stores an encrypted token, and account deletion sends revocation with the original token;
  - after the server restarts with a different key, deletion completes with 204, sends no revocation and logs the warning;
  - unlinking Apple with a damaged value completes and sends no revocation;
  - a plain-text token from before the change is gone after startup, and deletion of that account sends no revocation;
  - after a key change, the next Apple sign-in with an authorization code stores a fresh token that deletion then revokes (Decision 5);
  - the existing "tokens are not logged" test still passes.

## 4. Documentation

- [x] 4.1 In `server/README.md`, document:
  - `TOKEN_ENCRYPTION_KEY`, with how to generate it (`python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"`);
  - that it is required when Apple is configured;
  - storing it in AWS Secrets Manager or SSM Parameter Store and passing it as an environment variable;
  - what losing it means.

  Remove the "Encrypt the stored Apple refresh token" item from `todo.md`. Verify with `git diff`.

## 5. Integration and hand-off

- [x] 5.1 Run `uv run pytest -q` in `server/`. Verify that:
  - all tests pass, with the counts reported;
  - `openspec validate encrypt-apple-tokens --strict` passes;
  - the md5 of `app.db` is unchanged.
- [ ] 5.2 **Manual.** With a local server on a temporary storage root and the Apple consoles configured: sign in with Apple, check with `sqlite3` that the stored value starts with `v1:`, then delete the account and see the revocation in the log. This box stays unticked until someone runs it, because it needs the Apple Developer membership. It is part of the user's combined manual pass.
- [ ] 5.3 Push `feat/encrypt-apple-tokens`. Verify with `git ls-remote` that the remote branch matches the local HEAD.
