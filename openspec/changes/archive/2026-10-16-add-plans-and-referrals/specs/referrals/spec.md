# Spec Delta

## Purpose

Lets users invite friends with a personal code and rewards both sides with bonus generations, giving the product a growth loop without payments.

## ADDED Requirements

### Requirement: Give every account a referral code

The system SHALL give every account a unique referral code of 8 characters from an unambiguous uppercase alphabet, created with the account, and SHALL include it in `GET /me`. Accounts that existed before referrals were introduced SHALL receive a code when the server first starts afterwards. The code SHALL be stable for the life of the account.

#### Scenario: New account has a code

- **WHEN** a user registers and calls `GET /me`
- **THEN** the response contains an 8-character referral code

#### Scenario: Existing accounts are backfilled

- **WHEN** the server starts with accounts created before referral codes existed
- **THEN** each of those accounts has a unique referral code afterwards

### Requirement: Redeem a referral code at registration

The system SHALL accept an optional `referral_code` on `POST /auth/register`. Matching SHALL ignore letter case and surrounding spaces. When the code belongs to an account, the new account SHALL be linked to it. When the field is absent or blank, registration SHALL proceed without a referral. An unknown code SHALL be rejected with HTTP 400 and error `invalid_referral_code`, and no account SHALL be created.

#### Scenario: Valid code links the accounts

- **WHEN** a client registers with a new email and the referral code of an existing account, typed in lowercase
- **THEN** the system responds with HTTP 201
- **AND** the new account is linked to the referring account

#### Scenario: Unknown code is rejected

- **WHEN** a client registers with a code that matches no account
- **THEN** the system responds with HTTP 400 and error `invalid_referral_code`
- **AND** no account is created

#### Scenario: Registration without a code still works

- **WHEN** a client registers without a `referral_code`
- **THEN** the account is created and no bonus credits are granted

### Requirement: Reward both accounts

When an account is created with a valid referral code, the system SHALL add 5 bonus credits (configurable) to the new account. It SHALL also add 5 bonus credits to the referring account, unless that account has already been rewarded for 10 referrals (configurable), in which case only the new account is rewarded. Rewards SHALL be applied in the same step as account creation, so a failed registration grants nothing.

#### Scenario: Both accounts receive bonus credits

- **WHEN** a friend registers with a referring account's code
- **THEN** the friend's account has 5 bonus credits
- **AND** the referring account's bonus credits increased by 5

#### Scenario: Referrer cap is respected

- **WHEN** a referring account has already been rewarded for 10 referrals and another friend registers with its code
- **THEN** the new account receives 5 bonus credits
- **AND** the referring account's bonus credits are unchanged

#### Scenario: Deleting the friend does not reopen the cap

- **WHEN** a referring account was rewarded for 10 referrals and then some of those friends delete their accounts
- **THEN** the referring account still counts 10 rewards and is not rewarded again

### Requirement: Report referral progress

The system SHALL include in `GET /me` the account's referral code, how many referrals it has been rewarded for, the maximum rewarded referrals, and the bonus credits granted per referral.

#### Scenario: Progress is reported

- **WHEN** an account that has been rewarded for 3 referrals calls `GET /me`
- **THEN** the response reports 3 rewards, a maximum of 10, and 5 credits per referral
