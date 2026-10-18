# referrals Specification

## Purpose
Lets users invite friends with a personal code and rewards both sides with bonus generations, giving the product a growth loop without payments.

## Requirements

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

### Requirement: Report referral progress

The system SHALL include in `GET /me` the account's referral code, how many referrals it has been rewarded for, the maximum rewarded referrals, and the bonus credits granted per referral.

#### Scenario: Progress is reported

- **WHEN** an account that has been rewarded for 3 referrals calls `GET /me`
- **THEN** the response reports 3 rewards, a maximum of 10, and 5 credits per referral

### Requirement: Reward both accounts when the account is created

When an account is created from a registration that carried a valid referral code, the system SHALL add 5 bonus credits (configurable) to the new account. It SHALL also add 5 bonus credits to the referring account, unless that account has already been rewarded for 10 referrals (configurable) or no longer exists. Rewards SHALL be applied in the same step as the account's creation, at most once per account. A registration that is never confirmed SHALL earn nothing for either side.

#### Scenario: Both accounts receive bonus credits

- **WHEN** a friend registers with a referring account's code and then confirms the registration code
- **THEN** the friend's account has 5 bonus credits
- **AND** the referring account's bonus credits increased by 5

#### Scenario: Unconfirmed registration earns nothing

- **WHEN** a friend registers with a referring account's code and never confirms the registration code
- **THEN** the referring account's bonus credits and reward count are unchanged

#### Scenario: Rewards are paid only once

- **WHEN** a referred friend's account was created and the friend later completes a password reset
- **THEN** neither account receives further bonus credits

#### Scenario: Referrer cap is respected

- **WHEN** a referring account has already been rewarded for 10 referrals and another friend registers with its code and confirms
- **THEN** the new account receives 5 bonus credits
- **AND** the referring account's bonus credits are unchanged

#### Scenario: Referrer deleted before the friend confirms

- **WHEN** a friend registers with a referring account's code, the referring account is deleted, and the friend then confirms the registration code
- **THEN** the friend's account has 5 bonus credits

#### Scenario: Deleting the friend does not reopen the cap

- **WHEN** a referring account was rewarded for 10 referrals and then some of those friends delete their accounts
- **THEN** the referring account still counts 10 rewards and is not rewarded again

### Requirement: Redeem a referral code after a provider sign-up

The system SHALL expose `POST /me/referral`, for authenticated requests, taking a `code`. It SHALL accept it only from an account that was created through a sign-in provider less than 24 hours earlier and is not yet linked to a referrer; any other account SHALL get HTTP 409 with error `referral_not_allowed`. Code matching SHALL ignore letter case and surrounding spaces. A code that matches no account, or the account's own code, SHALL get HTTP 400 with error `invalid_referral_code`. On success the system SHALL link the accounts, apply the same rewards and referrer cap as "Reward both accounts when the account is created" immediately, and respond with HTTP 200.

#### Scenario: New provider account redeems a code

- **WHEN** an account created through Google 5 minutes ago posts a friend's code in lowercase
- **THEN** the system responds with HTTP 200
- **AND** the account has 5 bonus credits and the friend's bonus credits increased by 5

#### Scenario: Second redemption is refused

- **WHEN** a provider account that already redeemed a code posts another code
- **THEN** the system responds with HTTP 409 and error `referral_not_allowed`

#### Scenario: Password-registered account is refused

- **WHEN** an account registered with email and password posts a code
- **THEN** the system responds with HTTP 409 and error `referral_not_allowed`

#### Scenario: Window has passed

- **WHEN** an account created through Google 25 hours ago posts a code
- **THEN** the system responds with HTTP 409 and error `referral_not_allowed`

#### Scenario: Own or unknown code is rejected

- **WHEN** a new provider account posts its own referral code, or a code that matches no account
- **THEN** the system responds with HTTP 400 and error `invalid_referral_code`
- **AND** no credits change

#### Scenario: Referrer cap is respected

- **WHEN** the referring account has already been rewarded for 10 referrals
- **THEN** the redeeming account receives 5 bonus credits and the referring account's credits are unchanged
