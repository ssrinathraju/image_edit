## MODIFIED Requirements

### Requirement: Redeem a referral code after a provider sign-up

The system SHALL expose `POST /me/referral`, for authenticated requests, taking a `code`. It SHALL accept it only from an account that was created through a sign-in provider less than 24 hours earlier and is not yet linked to a referrer; any other account SHALL get HTTP 409 with error `referral_not_allowed`. Code matching SHALL ignore letter case and surrounding spaces. A code that matches no account, or the account's own code, SHALL get HTTP 400 with error `invalid_referral_code`. A code whose owner was itself referred by the redeeming account SHALL get HTTP 409 with error `referral_not_allowed`, and nothing SHALL change. On success the system SHALL link the accounts, apply the same rewards and referrer cap as "Reward both accounts when the account is created" immediately, and respond with HTTP 200.

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

#### Scenario: Mutual redemption is refused

- **WHEN** new provider account A redeems the code of new provider account B, and B then posts A's code
- **THEN** B's request gets HTTP 409 with error `referral_not_allowed`
- **AND** neither account's credits change from B's request
