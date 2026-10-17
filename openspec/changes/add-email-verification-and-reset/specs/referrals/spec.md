## MODIFIED Requirements

### Requirement: Reward both accounts

When an account created with a valid referral code first has its email verified, the system SHALL add 5 bonus credits (configurable) to that account. It SHALL also add 5 bonus credits to the referring account, unless that account has already been rewarded for 10 referrals (configurable) or no longer exists. Rewards SHALL be applied in the same step as the verification, at most once per account. An account that never verifies SHALL earn nothing for either side.

#### Scenario: Both accounts receive bonus credits

- **WHEN** a friend registers with a referring account's code and then verifies their email
- **THEN** the friend's account has 5 bonus credits
- **AND** the referring account's bonus credits increased by 5

#### Scenario: Unverified friend earns nothing

- **WHEN** a friend registers with a referring account's code and has not verified their email
- **THEN** the friend's account has 0 bonus credits
- **AND** the referring account's bonus credits and reward count are unchanged

#### Scenario: Verifying through a password reset pays the reward

- **WHEN** a friend registers with a referring account's code and then completes a password reset without having verified
- **THEN** the friend's account has 5 bonus credits
- **AND** the referring account's bonus credits increased by 5

#### Scenario: Rewards are paid only once

- **WHEN** a referred friend has verified their email and later completes a password reset
- **THEN** neither account receives further bonus credits

#### Scenario: Referrer cap is respected

- **WHEN** a referring account has already been rewarded for 10 referrals and another friend registers with its code and verifies their email
- **THEN** the new account receives 5 bonus credits
- **AND** the referring account's bonus credits are unchanged

#### Scenario: Referrer deleted before the friend verifies

- **WHEN** a friend registers with a referring account's code, the referring account is deleted, and the friend then verifies their email
- **THEN** the friend's account has 5 bonus credits

#### Scenario: Deleting the friend does not reopen the cap

- **WHEN** a referring account was rewarded for 10 referrals and then some of those friends delete their accounts
- **THEN** the referring account still counts 10 rewards and is not rewarded again

