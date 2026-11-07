# Proposal

## Why

Result images, which are face-derived, are served by a static mount at `/images/<job_id>.png` to anyone who has the link. Job ids are unguessable but ordered by time, and a link that leaks through logs, a proxy, a screenshot or a forwarded message works until the image is deleted 24 hours later. `todo.md` lists this as needed before any public deployment.

## What Changes

- **Signed links:** `result_url` becomes `/images/<job_id>.png?exp=<unix seconds>&sig=<signature>`. The signature is an HMAC-SHA256 over the job id and expiry, made with a server secret, and the link is valid for **15 minutes**.
- **Fresh links:** every status call for a succeeded job returns a newly signed link, so the app and the catch-up always get a fresh one.
- **Refused requests:** an unsigned, expired, tampered or other-job request gets the same 404 as an image that doesn't exist.
- **No caching beyond expiry:** image responses carry `Cache-Control: private, no-store`.
- **The secret:** a new `RESULT_URL_SECRET` setting. If it is empty, the server makes a random secret at startup, which is fine for one process because links only live 15 minutes. It must be set when several instances serve the same images.
- **App:** Reload on "Could not load the image." asks for the job's status again and uses the new link, so an expired link can be recovered. No other app change: the app already uses `result_url` exactly as given.

Out of scope:
- signing template preview URLs (they are public catalog images, not user data);
- binding a link to the account or device;
- a CDN or object storage;
- changing retention.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `photo-generation`: result URLs are signed, expire after 15 minutes and are freshly signed on each status call, and unsigned, bad or expired requests get 404.
- `generation-flow-ui`: Reload on an image that failed to load fetches a fresh link.

## Impact

- **Server:**
  - `services/worker.py` stores the plain path;
  - `generation_service.py` signs at response time;
  - new `core/url_signing.py` (pure HMAC functions);
  - a new `api/images.py` route replaces the `/images` `StaticFiles` mount in `main.py`;
  - the `RESULT_URL_SECRET` setting in `configs/settings.py` and `.env.example`;
  - `server/README.md`.
- **App:** `generation_status_screen.dart` (the Reload action) and its test.
- **Existing data:** none to migrate. Links issued before the upgrade stop working, and the app fetches a fresh one through status.
