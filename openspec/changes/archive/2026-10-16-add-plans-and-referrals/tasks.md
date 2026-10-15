# Tasks

Work on branch `feat/add-plans-and-referrals`. Do not push to `main`; open a PR at the end (group 10). Server tasks run in `server/`, app tasks in `app/`.

## 1. Server: settings and plan primitives

- [x] 1.1 Add `FREE_DAILY_LIMIT: int = 3`, `PREMIUM_DAILY_LIMIT: int = 30`, `REFERRAL_BONUS: int = 5`, `REFERRAL_MAX_REWARDS: int = 10` to `configs/settings.py`; verify `tests/configs/test_settings.py` asserts each default and one env override
- [x] 1.2 Add `core/plans.py` (`FREE`, `PREMIUM`, `ALL_PLANS`, `daily_limit(plan, settings)`, `plan_limits(settings)`) and `core/referral_codes.py` (`generate_code()` using the 32-character alphabet and `secrets.choice`, `normalize_code()`); verify `tests/core/test_plans.py` and `tests/core/test_referral_codes.py` cover limits per plan, an unknown plan raising, 8-character output from the allowed alphabet only, and normalization of case and spaces

## 2. Server: schema migration

- [x] 2.1 In `repos/user_store.py` add the new `users` columns, the `generation_usage` table and index, the unique `referral_code` index, and `_migrate()` per design Decision 2 (column checks via `PRAGMA table_info`, one transaction, backfill codes, set `user_version`); extend the `User` dataclass in `schemas/user.py` with `plan`, `bonus_credits`, `referral_code`, `referral_rewards`. Verify `tests/repos/test_user_store_migration.py` covers a fresh database, a database created by the previous schema with existing users and sessions (users keep their data, get `free`, 0 credits, and unique codes, sessions still resolve), and running the migration twice changing nothing
- [x] 2.2 Extract `auth_db_path(settings)` into `repos/user_store.py` and use it from `main.py`; verify the existing app-start test still passes and a test covers the empty-path default and an explicit `AUTH_DB_PATH`

## 3. Server: store operations

- [x] 3.1 Add `reserve_generation`, `refund_generation`, and `usage_snapshot(user_id, daily_limit, now)` to `SqliteUserStore` and the `UserStore` Protocol, with `QuotaExceeded` in `core/user_store.py`, per design Decisions 3 and 4. Verify `tests/repos/test_user_store_usage.py` covers daily use then bonus use then `QuotaExceeded`, UTC rollover via the injected clock, refund of a daily and of a bonus reservation, refund being idempotent, a refund from a previous day not changing today, and two threads racing for the last generation with exactly one winning
- [x] 3.2 Add `register_user(email, password_hash, referral_code, bonus, max_rewards)` to the store, with `InvalidReferralCode`, per design Decision 6, replacing `create_user` for registration (keep `create_user` for tests that need a bare user); clear `referred_by` of dependents in `delete_user`. Verify `tests/repos/test_user_store_referrals.py` covers a valid code rewarding both, a lowercase code with spaces, an unknown code writing nothing, a duplicate email rolling back the referrer's reward, the cap rewarding only the friend, deleting a friend not reopening the cap, and deleting a referrer clearing `referred_by`

## 4. Server: quota in the generation flow

- [x] 4.1 Add `services/quota_service.py` (`reserve(user)`, `release(reservation_id)`, `summary(user)` building the `usage` object with `remaining`, `resets_at`, and `plan_limits`); add `Job.reservation_id`; verify `tests/services/test_quota_service.py` covers the summary arithmetic, `resets_at` being the next 00:00 UTC, and the premium limit
- [x] 4.2 Integrate into `generation_service.submit`: reserve after validation and before creating the job (via `asyncio.to_thread`), store the reservation id on the job, release on any exception before the job is queued, and map `QuotaExceeded` to `429 {"error": "quota_exceeded", ...}`. Verify `tests/api/test_generations_quota.py` covers three accepted then a fourth 429 with no job created, validation failures not consuming a generation, a bonus credit covering the fourth, premium allowing a fourth, and an upload failure releasing the reservation
- [x] 4.3 In `services/worker.py` refund the reservation when a job becomes `failed` (not for dropped or succeeded jobs); verify `tests/services/test_worker.py` covers a failing pipeline restoring the generation, a succeeding one not, and a bonus-paid failure restoring the credit
- [x] 4.4 Verify end to end in `tests/integration/test_quota_flow.py`: register, use the allowance with the stub pipeline, get 429, restart the app on the same storage directory and still get 429

## 5. Server: referrals and `/me`

- [x] 5.1 Add `services/referral_service.py` (`summary(user)`) and wire registration: `Credentials` gains an optional `referral_code` (max 32 characters), `auth_service.register` calls `register_user` with the settings values and maps `InvalidReferralCode` to `400 invalid_referral_code`; verify `tests/services/test_auth_service.py` and `tests/api/test_auth.py` cover the three referral scenarios in `specs/referrals/spec.md` through HTTP
- [x] 5.2 Extend `MeResponse` and `GET /me` with `plan`, `usage`, and `referral` per design Decision 7; verify `tests/api/test_me.py` covers a fresh account (3 limit, 0 used, code present), one that used 2 and holds 5 credits (6 remaining), and that no password material is returned
- [x] 5.3 Verify with `tests/integration/test_referral_flow.py`: user A registers, user B registers with A's code in lowercase, both show 5 bonus credits on `/me`, B uses 3 daily then a 4th is accepted from the bonus, and an 11th friend of A is rewarded while A is not

## 6. Server: operator tooling and docs

- [x] 6.1 Add `scripts/set_plan.py --email <email> --plan free|premium` using `auth_db_path(Settings())`, with a clear error for an unknown email or plan; verify `tests/scripts/test_set_plan.py` covers success, unknown email, unknown plan, and that a running store sees the change on its next read
- [x] 6.2 Update `server/README.md`: the new settings, the `429 quota_exceeded` error, the extra `/me` fields, the optional `referral_code` on register with a curl example, the `set_plan.py` usage, and the note that the first start upgrades an existing `app.db`; verify each curl example by running it against a local server

## 7. App: models, client, providers

- [x] 7.1 Add `schemas/account.dart` (`Plan`, `Usage` with `dailyLimit`, `usedToday`, `bonusCredits`, `remaining`, `resetsAt`, `planLimits`, and `Referral`), extend `UserProfile` and `fetchMe` to parse the new fields while tolerating their absence, and add `referralCode` to `register`; verify `test/schemas/account_test.dart` and `test/core/api_client_test.dart` cover full and minimal `/me` payloads and the register body with and without a code (omitted when blank)
- [x] 7.2 Add `features/plans/account_notifier.dart` (`AccountNotifier` loading `/me`, resetting on sign-out, `refresh()`); verify `test/features/plans/account_notifier_test.dart` covers load, refresh after a usage change, and reset when the session ends
- [x] 7.3 Add `AppConfig.inviteUrl` and `INVITE_URL=` to `.env.example` and `.env`; add `core/api_errors.dart` with `errorCodeOf(error)`; verify `test/configs/app_config_test.dart` and `test/core/api_errors_test.dart` cover blank and set values and extracting `quota_exceeded` from a 429 response

## 8. App: registration, home chip, limit dialog

- [x] 8.1 Add the optional referral code field to `register_screen.dart` (trimmed, keeps entered values on failure, shows the server message for an unknown code); verify `test/features/auth/register_screen_test.dart` covers the code being sent, omitted when blank, and the error keeping email and password
- [x] 8.2 Add a remaining-generations chip to `home_screen.dart` reading `accountProvider` (hidden while loading or when the data is missing), refreshed after each submission and after a status poll reaches `failed`; verify `test/features/home/home_screen_test.dart` covers the figure with bonus credits and the update after a submission
- [x] 8.3 Add `features/plans/limit_reached_dialog.dart` and handle `quota_exceeded` in `submit_flow.dart` (refresh the account, show the dialog with the reset time in local time and Upgrade and Invite friends buttons, keep the photo and prompt); verify `test/features/common/submit_flow_test.dart` covers the dialog appearing, the form values being kept, and the buttons navigating to the Upgrade and Invite screens

## 9. App: profile plan card, Upgrade, Invite

- [x] 9.1 Add the plan and usage card to `profile_screen.dart` (plan name, used of limit, bonus credits, Upgrade action only on `free`); verify `test/features/profile/profile_plan_card_test.dart` covers the free and premium variants
- [x] 9.2 Add `features/plans/upgrade_screen.dart` (route `/upgrade`; Free vs Premium limits from `plan_limits`, "Payments are not available yet", no purchase control); verify its widget test asserts the figures and that there is no button that submits anything
- [x] 9.3 Add `features/plans/invite_screen.dart` (route `/invite`; code, "N of M friends rewarded", Share opening the share sheet with the message from design Decision 8 through an injectable share function); verify its widget test covers the displayed progress and the shared text containing the code and the optional invite URL
- [x] 9.4 Add the Upgrade and Invite friends entries to the profile and route them; verify `flutter analyze` is clean and the router test reaches both screens from the profile

## 10. Integration and PR

- [x] 10.1 Run `uv run pytest` in `server/` and `flutter analyze && flutter test` in `app/`; verify all pass with zero analyzer warnings, then run `openspec validate add-plans-and-referrals --strict`
- [ ] 10.2 Manual run on the iOS simulator with a local server started on a copy of an existing `app.db`: the upgrade keeps the old account working → home shows 3 left → use 3 → limit dialog with reset time → Invite friends shows the code → register a second account with that code (both show +5) → generate with bonus → promote an account with `set_plan.py` and see Premium on the profile without restarting. Leave this box unchecked if any step could not be run and say which in the PR
- [x] 10.3 Push the branch and open a PR to `main` with a summary, the test plan, and which steps of 10.2 were exercised
