# Spec Delta

## MODIFIED Requirements

### Requirement: Create an account

The app SHALL provide a registration screen reachable from the sign-in screen, taking an email, a password of at least 8 characters, and an optional referral code, with an inline message when the password is too short. On success the app SHALL sign the user in and show the home screen; when the email is taken or the referral code is not recognised it SHALL say so and keep the entered values.

#### Scenario: Registration signs the user in

- **WHEN** the user submits a new email and a valid password
- **THEN** the app shows the home screen as that user

#### Scenario: Short password is blocked

- **WHEN** the user enters a password shorter than 8 characters
- **THEN** an inline message is shown and the submit control is disabled

#### Scenario: Taken email is reported

- **WHEN** the user registers an email that already has an account
- **THEN** the screen stays open and says the email is already registered

#### Scenario: Referral code is optional and sent when entered

- **WHEN** the user enters a referral code along with a valid email and password and submits
- **THEN** the app sends the code with the registration
- **AND** the new account shows the bonus generations on the home screen

#### Scenario: Unknown referral code is reported

- **WHEN** the user submits a referral code the server does not recognise
- **THEN** the screen stays open, says the code was not recognised, and keeps the entered email and password

## ADDED Requirements

### Requirement: Show remaining generations on the home screen

The home screen SHALL show how many generations the user has left today, including any bonus credits. The figure SHALL update after each submission and when a job ends in failure.

#### Scenario: Remaining count is shown

- **WHEN** a free user with 3 daily generations and no bonus credits opens the home screen
- **THEN** the screen shows 3 generations left

#### Scenario: Count updates after a submission

- **WHEN** the user submits a generation and returns to the home screen
- **THEN** the remaining count is one lower

### Requirement: Explain the limit when it is reached

When the server refuses a generation because the limit is reached, the app SHALL stay on the current screen and show a dialog that says the daily limit is reached, when it resets, and offers Upgrade and Invite friends. The user's photo and prompt SHALL be kept.

#### Scenario: Limit dialog is shown

- **WHEN** the user taps Generate and the server answers `quota_exceeded`
- **THEN** a dialog explains the limit and the reset time and offers Upgrade and Invite friends
- **AND** the photo and prompt are still on the screen after the dialog is closed

### Requirement: Show the plan and usage on the profile screen

The profile screen SHALL show a card with the account's plan, generations used today against the daily limit, and bonus credits, and an Upgrade action when the plan is free.

#### Scenario: Free plan card

- **WHEN** a free user who used 2 of 3 generations and holds 5 bonus credits opens the profile
- **THEN** the card shows the Free plan, 2 of 3 used, 5 bonus credits, and an Upgrade action

#### Scenario: Premium plan has no Upgrade action

- **WHEN** a premium user opens the profile
- **THEN** the card shows the Premium plan and no Upgrade action

### Requirement: Show what Premium offers

The Upgrade screen SHALL compare the Free and Premium plans by their daily limits and SHALL state clearly that payments are not available yet. It SHALL NOT collect payment details or imply that a purchase can be completed.

#### Scenario: Upgrade screen explains the plans

- **WHEN** the user opens the Upgrade screen
- **THEN** it shows the Free and Premium daily limits and a notice that payments are not available yet

### Requirement: Invite friends with a referral code

The profile screen SHALL provide an Invite friends action that shows the user's referral code, how many friends have been rewarded out of the maximum, and opens the system share sheet with a message that contains the code.

#### Scenario: Share sheet carries the code

- **WHEN** the user taps Invite friends and then Share
- **THEN** the system share sheet opens with a message containing the user's referral code

#### Scenario: Progress is shown

- **WHEN** a user who has been rewarded for 3 of 10 referrals opens Invite friends
- **THEN** the screen shows 3 of 10 friends rewarded
