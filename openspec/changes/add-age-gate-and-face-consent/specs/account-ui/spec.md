## MODIFIED Requirements

### Requirement: Register with email and password

The app SHALL provide a registration screen reachable from the sign-in screen, taking an email, a password of at least 8 characters, a date of birth chosen with a date picker, and an optional referral code, with an inline message when the password is too short. The submit control SHALL be disabled until a date of birth is chosen. When the server answers `under_age`, the screen SHALL say "You must be 18 or older to use this app" and keep the other entered values. On success the app SHALL show the Confirm registration screen for that email, without signing in; when the email is taken or the referral code is not recognised it SHALL say so and keep the entered values.

#### Scenario: Registration asks for the emailed code

- **WHEN** the user submits a new email and a valid password
- **THEN** the app shows the Confirm registration screen for that email
- **AND** no session is stored

#### Scenario: Short password is blocked

- **WHEN** the user enters a password shorter than 8 characters
- **THEN** an inline message is shown and the submit control is disabled

#### Scenario: Taken email is reported

- **WHEN** the user registers an email that already has an account
- **THEN** the screen stays open and says the email is already registered

#### Scenario: Referral code is optional and sent when entered

- **WHEN** the user enters a referral code along with a valid email and password and submits
- **THEN** the app sends the code with the registration
- **AND** after the user confirms the registration code, the home screen shows the bonus generations

#### Scenario: Unknown referral code is reported

- **WHEN** the user submits a referral code the server does not recognise
- **THEN** the screen stays open, says the code was not recognised, and keeps the entered email and password

#### Scenario: Date of birth is required

- **WHEN** the user has entered an email and a valid password but no date of birth
- **THEN** the submit control is disabled

#### Scenario: Under-18 is refused

- **WHEN** the user submits a date of birth under 18
- **THEN** the screen says "You must be 18 or older to use this app" and keeps the email and password

## ADDED Requirements

### Requirement: Ask a new provider account for its date of birth

When the server answers a Google or Apple sign-in with `age_required`, the app SHALL show a date-of-birth screen and, on Continue, send the same sign-in again with the chosen date. An `under_age` answer SHALL show "You must be 18 or older to use this app" and return to the sign-in screen with no session. Cancelling SHALL return to the sign-in screen with no session.

#### Scenario: New Google user gives a date of birth

- **WHEN** a new user taps Continue with Google and the server answers `age_required`
- **THEN** the date-of-birth screen is shown
- **AND** after choosing an adult date and tapping Continue, the user is signed in

#### Scenario: Under-18 provider sign-up

- **WHEN** the user chooses a date under 18 on the date-of-birth screen
- **THEN** the app says "You must be 18 or older to use this app" and shows the sign-in screen with no session

### Requirement: Confirm the age of an existing account

When the signed-in account's age is not confirmed, the app SHALL show a Confirm your age screen before any other signed-in screen. Submitting an adult date SHALL confirm it and show the home screen. An under-18 date SHALL show a screen saying the account cannot be used, offering Delete account and Sign out.

#### Scenario: Unconfirmed account is asked first

- **WHEN** an account whose age is not confirmed signs in
- **THEN** the Confirm your age screen is shown instead of the home screen

#### Scenario: Adult date opens home

- **WHEN** the user submits a date at least 18 years before today
- **THEN** the home screen is shown and the screen is not shown again

#### Scenario: Under-18 date blocks the account

- **WHEN** the user submits a date under 18
- **THEN** the app says the account cannot be used and offers Delete account and Sign out only

### Requirement: Ask for face-photo consent before the first upload

Before submitting a generation, when the account has not accepted the current consent version, the app SHALL show a consent screen. It SHALL explain:
- that the photo is used for this generation only and deleted after the job;
- that the result is kept on the server for 24 hours;
- that creations are stored on this device;
- that the user may only upload photos of themselves or of people who agreed.

It SHALL link to the privacy policy. Accepting SHALL record consent for the current version and continue the submission with the same photo and prompt. Declining SHALL return to the form with the photo and prompt kept and nothing submitted. A server refusal with `consent_required` SHALL also open the consent screen.

#### Scenario: First submit asks for consent

- **WHEN** an account without consent submits a generation
- **THEN** the consent screen is shown before anything is uploaded

#### Scenario: Accepting continues the submission

- **WHEN** the user accepts on the consent screen
- **THEN** the generation is submitted with the same photo and prompt and the status screen opens

#### Scenario: Declining submits nothing

- **WHEN** the user declines on the consent screen
- **THEN** the form shows the same photo and prompt and no generation was submitted

#### Scenario: New consent version asks again

- **WHEN** the account accepted version "1" and the server's current version is "2"
- **THEN** the next submission shows the consent screen again

### Requirement: Show and withdraw face-photo consent on the profile

The profile screen SHALL show a Face photo consent row, reading "Given on <date>" with a Withdraw action when the current version is accepted, and "Not given" otherwise. Withdraw SHALL ask for confirmation and then withdraw consent on the server.

#### Scenario: Withdraw from the profile

- **WHEN** the user taps Withdraw and confirms
- **THEN** the row reads "Not given"
- **AND** the next submission shows the consent screen

