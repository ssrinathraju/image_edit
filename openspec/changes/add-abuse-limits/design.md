# Design

## Context

- **Registration today:** `POST /auth/register` checks the date of birth and the email format, then the referral code. It holds a pending registration and emails a code, limited per address by the email-codes sending limits (`too_many_requests`).
- **Provider sign-ins:** `POST /auth/oauth/{google|apple}` find, link or create an account. A new account needs a date of birth.
- **Email change:** `POST /me/email` sends a code to the new address.
- **Referrals after a provider sign-up:** `POST /me/referral` lets an account created through a provider in the last 24 hours redeem one code.
- **Existing throttle:** the only one is `LoginThrottle`, which is per email, in memory and per process.
- **Deployment:** the server will sit behind an AWS load balancer.

## Decisions

### Decision 1: The disposable list is a seed file, matched by domain suffix
`seed/abuse/disposable_domains.txt` has one lower-case domain per line, and `#` comments are allowed. The starter list is taken from the public-domain (CC0) `disposable-email-domains` project, and its source and date go in a header comment. `core/disposable_domains.py` loads it into a `frozenset` at startup.

`is_disposable(email)` lower-cases the domain after the last `@`. It then checks the domain and each parent (`a.b.c`, `b.c`, `c`) against the set. A missing or unreadable file fails startup and names the file (`DISPOSABLE_DOMAINS_FILE`, default `./seed/abuse/disposable_domains.txt`).

The check runs after the email format check and before the referral and sending checks, so nothing is stored or sent for a refused address. Provider sign-ins skip it, because the provider has verified the address, and Apple relay addresses must work.

**Rejected:** a third-party verification API. It sends user email addresses to another company, and it adds a network dependency to registration.

**Rejected:** an MX-record lookup. It is slow, unreliable, and easy to get around.

### Decision 2: Per-address limits live in memory, in a sliding window
`SignupLimiter` keeps, for each address, a `deque` of the times of counted requests, and drops entries older than 24 hours.
- `check(address, now)` returns `None` when the request is allowed. Otherwise it returns the seconds to wait: until the oldest entry inside the hour leaves when the hour has 5 entries, or the same for the day when it has 10.
- `record(address, now)` is called only after the request was accepted, meaning the 202 for registration or the account created for a provider sign-up.
- A `threading.Lock` guards the map, and entries that age out are removed, so memory is bounded by recent sign-ups.

The limiter is created once in `create_app`.

**Rejected:** a SQLite table. It would store network addresses, which are personal data, on disk, and it isn't needed for one process. The cost is that a restart clears the counts, which is accepted. A shared store such as Redis or the database becomes necessary with several instances; that is recorded as a deployment follow-up.

The limits (5 per hour and 10 per day) are constants in `core/signup_limiter.py`, as the user chose. They aren't settings (CLAUDE.md §3).

### Decision 3: The client address uses a trusted-hop count
`client_address(request, hops)` works like this:
- with `hops == 0`, it returns `request.client.host`;
- otherwise it splits `X-Forwarded-For` on commas, strips each part, and returns the entry `hops` from the right;
- if the header has fewer entries, it falls back to `request.client.host`.

`TRUSTED_PROXY_HOPS: int = Field(default=0, ge=0, le=5)`. An AWS ALB appends the real client address, so `1` is correct behind one ALB, and the README says so. Entries to the left of the trusted hop are attacker-controlled, so they are never used.

**Rejected:** always trusting the first `X-Forwarded-For` entry. Any client could set it and get around the limit. The user chose the hop count.

**Rejected:** Starlette's `ProxyHeadersMiddleware`. It trusts by proxy address, not by hop count, which suits a load balancer with changing addresses less well.

### Decision 4: The referral cycle check is in the service, before any change
`ReferralService.redeem` refuses the code with 409 `referral_not_allowed` when the code's owner has `referred_by == redeemer.id`. The check runs inside the same store transaction as the redemption, so two simultaneous redemptions can't both pass. It uses the existing `referred_by` column, so there is no schema change.

### Decision 5: Distinct error codes, so the app can say the right thing
- `disposable_email` (400): its detail reads "Use a permanent email address.".
- `too_many_signups` (429, `Retry-After`): it is kept apart from `too_many_requests`, which the app reads as "too many codes requested", so the message is right.

The app maps both codes in `core/api_errors.dart`. The register screen, the change email screen and the provider sign-in error path show the messages from the spec and keep the form contents. The wait is shown in minutes when it is 60 seconds or more, rounded up, and in seconds otherwise.

### Decision 6: What counts as a "provider sign-in that creates an account"
The count is made where `auth_service` would insert a new user for a provider identity. That is after the identity is verified, and after the existing find or link has found no account. An existing account, or a link to an existing account by email, is never counted or limited. If the limit applies, nothing is created and the provider token is discarded.

## Screens and states

| Screen | New states |
|---|---|
| Register | `disposable_email`: "Use a permanent email address.", fields kept. `too_many_signups`: "Too many new accounts from this network. Try again in N minutes." (or seconds), fields kept. |
| Change email | `disposable_email`: "Use a permanent email address.", field kept. |
| Sign-in (Google or Apple buttons) and the provider age screen | `too_many_signups`: the same message, and the user stays signed out. |

## Risks and trade-offs

- **Data stored:**
  - network addresses and timestamps, in memory only, for at most 24 hours, then dropped;
  - the disposable list, a public file in the repo.
- **Who can read it:** nobody through any API. The counts are inside the server process.
- **Logging:**
  - a refusal logs `signup_limited` at INFO with the retry seconds, and no address or email;
  - a disposable refusal logs `disposable_email_refused` with the domain only, not the full address. A domain on the list is not personal data.
- **Migration:** none. Existing accounts with disposable addresses keep working; reviewing them is out of scope.
- **False positives:**
  - Shared addresses (mobile carriers using CGNAT, offices) can reach 5 per hour. The message explains the wait.
  - The disposable list can include domains some real people use. The file is easy to edit, and a change applies at restart.
- **Failure and retry:** a refused request changes nothing and can be retried after `Retry-After`. A limiter error is a bug; it is not caught, so it surfaces as a 500 in tests rather than silently letting requests through.
- **Background tasks:** none. Entries that age out are removed during `check` and `record`.
- **Thread-safety:** the limiter's map is guarded by its lock. The referral cycle check runs inside the store transaction.
- **Several instances:** each process would count separately, effectively multiplying the limit. This is recorded as a deployment checklist item, alongside the move to Postgres.
