# Tasks

Work on branch `feat/sign-result-urls`. Do not push to `main`. This builds on `upgrade-server-python`: merge `origin/main` first and run on Python 3.11. "Decision N" refers to `design.md`. Tests use temporary storage roots. Record the md5 of `server/storage/app.db` before and after each full test run.

## 1. Signing

- [ ] 1.1 Add `core/url_signing.py` with `sign`, `verify` and `RESULT_URL_TTL` (Decisions 1 and 4). Verify in `tests/core/test_url_signing.py`:
  - a round trip;
  - an expired `exp`;
  - a changed `exp`;
  - another job's signature;
  - a wrong secret;
  - a malformed signature (not base64, the wrong length);
  - comparison uses `hmac.compare_digest`. Check this with a monkeypatch spy, or by code inspection noted in the test.
- [ ] 1.2 Add the `RESULT_URL_SECRET` setting with startup handling (Decision 3): random when empty; startup fails when set but shorter than 32 characters. Document it in `.env.example`. Verify in `tests/test_main.py`:
  - empty gives a working app whose links verify;
  - a short secret fails startup with a clear message;
  - a configured secret makes links from two app instances interchangeable;
  - the secret never appears in the logs (`caplog`).

## 2. Serving and status

- [ ] 2.1 Sign `result_url` in `generation_service` for each succeeded status response. The worker must not store a signed URL (Decision 1). Verify in `tests/services/test_generation_service.py` or the API tests:
  - the URL has `exp` and `sig`;
  - two calls 20 minutes apart (with a fake clock) give different, later expiries;
  - queued, running and failed jobs have no `result_url`.
- [ ] 2.2 Replace the `/images` `StaticFiles` mount with `api/images.py` (Decision 2). Verify in `tests/api/test_images.py` that a valid link gives 200 with `image/png` and `Cache-Control: private, no-store`. Each of these gives the same 404 body:
  - no parameters;
  - an expired link (fake clock past 15 minutes);
  - a tampered `exp`;
  - another job's `sig`;
  - a non-numeric or over-long `exp`;
  - a bad `job_id` (`..%2F`, uppercase, other characters);
  - a swept file with a valid link;
  - a content-blocked job, which never had a file promoted.

  The existing retention, content-safety and status API tests must pass with signed links.

## 3. App

- [ ] 3.1 Make the status screen's Reload refetch status before reloading the image (Decision 5). Verify in `test/features/generation_status/generation_status_screen_test.dart`, with a fake service:
  - the first image fetch fails;
  - Reload calls status again and loads the bytes from the new URL;
  - when that status call fails, the failure view with Home is shown;
  - the existing Reload, save and expiry-note tests still pass.

## 4. Documentation

- [ ] 4.1 In `server/README.md`, document:
  - signed result links and their 15-minute lifetime;
  - `RESULT_URL_SECRET` (random when empty; required for several instances);
  - that access logs show the `sig` parameter, and how to disable uvicorn's access log in production.

  Remove the "Authenticated or signed image URLs" item from `todo.md`. Verify with `git diff` that only those lines changed.

## 5. Integration and hand-off

- [ ] 5.1 Run `uv run pytest -q` in `server/` on Python 3.11, and `flutter analyze && flutter test` in `app/`. Verify that all tests pass, with counts reported, that `openspec validate sign-result-urls --strict` passes, and that the md5 of `app.db` is unchanged.
- [ ] 5.2 **Manual.** Use a local server in log mode on a temporary storage root, with the iOS simulator and the Android emulator:
  - generate and see the image;
  - copy the `result_url` from the server log or a status call with curl. It works at once, and gives 404 after 15 minutes or with `sig` changed;
  - leave a result screen open past 15 minutes and tap Reload where the image failed, if it can be forced. The image comes back;
  - My creations catch-up still saves results.

  This box stays unticked until someone runs it. It is part of the user's combined manual pass.
- [ ] 5.3 Push `feat/sign-result-urls`. Verify with `git ls-remote` that it matches the local HEAD.
