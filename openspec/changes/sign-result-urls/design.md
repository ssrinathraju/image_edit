# Design

## Context

- **How images are served today:** `main.py` mounts `StaticFiles` at `/images` over `<STORAGE_ROOT>/outputs`. The worker sets `result_url=f"/images/{job_id}.png"` when a job succeeds, and `generation_service` copies it into the status response.
- **Where images live:** images are promoted from staging to `outputs/` only after the safety check, and the retention sweep deletes them after `OUTPUT_RETENTION_HOURS` (24).
- **How the app uses the link:**
  - it resolves `result_url` against its base URL and downloads the bytes with Dio (`fetchImageBytes`);
  - the status screen caches the bytes per URL (`resultImageBytesProvider`), and its Reload invalidates only that cache;
  - the catch-up (`HistorySync`) calls status, then fetches the image;
  - share and download use the bytes, never the URL.
- **Process model:** the server runs as one process.

## Decisions

### Decision 1: HMAC-signed query parameters, signed per response
`core/url_signing.py` has pure functions:
- `sign(job_id, expires_at, secret) -> str`: the HMAC-SHA256 of `f"{job_id}:{exp}"`, base64url-encoded without padding;
- `verify(job_id, exp, sig, secret, now) -> bool`: `hmac.compare_digest`, and `exp > now`.

`generation_service` builds `result_url = f"/images/{job_id}.png?exp={exp}&sig={sig}"` each time it answers a status call for a succeeded job, with `exp = now + 15 min`. The worker keeps storing the unsigned path, or nothing, so a stored record never carries a signature.

**Rejected:** bearer authentication on `/images`. It would break any use of the link outside the app's authenticated client, for no gain, because the link is already handed only to the job's owner. The user chose signed links.

**Rejected:** signing once, when the job succeeds. That would need either a long expiry or a re-sign step anyway. Signing per response keeps every link short-lived.

### Decision 2: One route replaces the static mount
`api/images.py` defines `GET /images/{job_id}.png`:
1. Check that `job_id` matches the job-id pattern; otherwise 404.
2. Parse `exp` as a whole number and check it isn't longer than 12 digits; otherwise 404.
3. Verify the signature; otherwise 404.
4. Check that the file `outputs/<job_id>.png` exists; otherwise 404.
5. Return a `FileResponse` with `image/png` and `Cache-Control: private, no-store`.

All failures give the same 404 body, so a caller can't tell a bad signature from a missing image. The check doesn't load the job record, because the file's existence is the retention truth, which also covers jobs whose records have expired.

**Rejected:** keeping `StaticFiles` with middleware in front of it. It splits the logic across two places, and it's harder to give every case the same 404.

### Decision 3: Secret from settings, random by default
`RESULT_URL_SECRET: str = ""`. When it is empty, `create_app` generates 32 random bytes with `secrets.token_bytes` and logs at INFO that a random secret is in use, without the secret itself. When it is set, it must be at least 32 characters, or startup fails with a clear message. `.env.example` documents it and leaves it empty.

A restart invalidates outstanding links, which is harmless: they live 15 minutes, and the app refetches status.

**Rejected:** a required secret. It adds a deployment step with no benefit for one process. It must be set before several instances serve the same `outputs/`, which the README states.

### Decision 4: 15-minute lifetime, as a constant
`RESULT_URL_TTL = timedelta(minutes=15)` lives in `core/url_signing.py`. The user chose 15 minutes, and nothing needs to tune it, so it isn't a setting (CLAUDE.md §3).

### Decision 5: The app's Reload refetches status
In `_SuccessView`, the Reload action invalidates `generationStatusProvider(jobId)` as well as the bytes cache, so the next build gets a new `result_url` and loads from it. Everything else stays as it is. `HistorySync` already calls status right before each fetch, so it always has a fresh link.

**Rejected:** retrying automatically on 404. It hides real deletions behind a loop. One explicit Reload is clear and easy to test.

## Screens and states

| Screen | States |
|---|---|
| Status screen, after success | Loading the image; image shown (unchanged); "Could not load the image." with Reload, which now refetches status and then loads the new link. If status itself then fails, the existing failure view is shown with Home. |

## Risks and trade-offs

- **Data stored:** none new. The secret lives only in memory, or in the environment when it's set, and is never written to disk by the server.
- **Who can read an image:** anyone holding a link, for at most 15 minutes. Links are given only to the job's owner, through the owner-scoped status endpoint.
- **Logging:**
  - signatures and the secret are never logged;
  - refused requests are not logged one by one, so a scan can't fill the log;
  - uvicorn's access log prints request paths with query strings, which includes `sig`. The signature is harmless once expired, but the README notes it, and the access log can be turned off in production.
- **Migration:** none. Old unsigned links get 404 after the upgrade, and the app recovers through status or Reload.
- **Failure and retry:**
  - an expired link gives 404, and the user recovers with Reload (Decision 5);
  - the catch-up refetches status each run.
- **Clock skew:** `exp` is checked against the server's own clock, which is also the one that issued it, so client clocks don't matter.
- **Background tasks:** the retention sweep is unchanged. A signed link to a swept file gives 404.
- **Thread-safety:** the signing functions are pure, and the secret is read-only after startup.
- **Path safety:** the `job_id` pattern check comes before any file-system access, so `../` and other path tricks are refused.
