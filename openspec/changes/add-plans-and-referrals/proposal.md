# Proposal

## Why

Every generation costs real GPU time, and today a signed-in user can submit without limit. The app also has no growth loop. This change (2 of 3) gives each account a plan with a daily generation allowance, so cost has a ceiling and Upgrade has a reason to exist, and adds referral codes that reward both sides with bonus generations. Payments are deliberately deferred, so Premium is switched on by the operator for now.

## What Changes

- **Plans**: each account is on `free` (3 generations per day) or `premium` (30 per day). Both numbers are server settings.
- **Daily allowance**: the count resets at 00:00 UTC. A generation that ends `failed` is refunded; one that succeeds is not.
- **Enforcement**: `POST /generations` reserves one generation before enqueueing and answers `429 quota_exceeded` when the allowance and any bonus credits are used up. Requests that fail validation never consume allowance.
- **Bonus credits**: one-time, non-expiring credits that are spent only after the daily allowance is used up.
- **Referrals**: every account gets a referral code. A new user may enter a code when registering; both accounts receive 5 bonus credits. A referrer is rewarded for at most 10 friends; the friend is always rewarded.
- **`GET /me`** additionally returns the plan, usage (limit, used today, bonus credits, remaining, next reset), and the account's referral code and reward count.
- **`POST /auth/register`** accepts an optional `referral_code`; an unknown code is rejected with 400.
- **Operator tooling**: `server/scripts/set_plan.py` changes an account's plan. There is no public endpoint for it.
- **App**:
  - Registration gets an optional referral code field.
  - Home shows how many generations are left today.
  - A limit dialog appears when the server says the limit is reached, offering Upgrade and Invite friends.
  - Profile gets a plan card with Upgrade, and Invite friends (share sheet with the code).
  - The Upgrade screen compares Free and Premium and states that payments are not available yet.
- **Migration**: the existing `app.db` is upgraded in place at startup (new columns, a usage table, and referral codes backfilled for existing users).

Out of scope: payments and store billing, receipts, plan expiry or renewal, redeeming a code after sign-up, email verification, an admin UI, usage history, and per-template limits.

## Capabilities

### New Capabilities

- `usage-quota`: Plans, the daily allowance and its UTC reset, bonus credits, reservation and refund of generations, and the limit-reached response.
- `referrals`: Referral codes, redeeming a code at registration, and the bonus rewards with their cap.

### Modified Capabilities

- `user-auth`: Registration accepts an optional referral code; `GET /me` also returns plan, usage, and referral details.
- `account-ui`: Registration screen gets the referral field; the profile shows the plan and usage and offers Upgrade and Invite friends; the limit-reached dialog.

## Impact

- **Server**: changes to `repos/user_store.py` (migration, plan, usage ledger, bonus credits, referral columns), `core/user_store.py`, `schemas/user.py`, `services/auth_service.py`, `services/generation_service.py`, `services/worker.py`, `api/auth.py`, `api/generations.py`, `main.py`, `configs/settings.py`; new `services/quota_service.py`, `services/referral_service.py`, and `scripts/set_plan.py`. No new Python dependencies.
- **Data**: new columns on `users` and a `generation_usage` table in the existing SQLite file. Jobs stay in memory; the usage ledger is persistent so a restart does not reset anyone's allowance.
- **App**: `schemas/session.dart` (profile and usage models), `core/api_client.dart`, `features/auth/register_screen.dart`, `features/home/`, `features/profile/`, and new `features/plans/` (usage provider, limit dialog, upgrade screen). No new app dependencies (`share_plus` is already present).
- **APIs**: additive fields on `GET /me`; one optional field on register; one new error, `429 quota_exceeded`, on `POST /generations`.
- **Depends on**: change 1 (accounts) only. Generation history is change 3.
