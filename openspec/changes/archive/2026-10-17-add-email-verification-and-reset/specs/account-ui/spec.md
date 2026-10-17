## MODIFIED Requirements

### Requirement: Create an account

The app SHALL provide a registration screen reachable from the sign-in screen, taking an email, a password of at least 8 characters, and an optional referral code, with an inline message when the password is too short. On success the app SHALL sign the user in and show the Verify email screen; when the email is taken or the referral code is not recognised it SHALL say so and keep the entered values.

#### Scenario: Registration signs the user in

- **WHEN** the user submits a new email and a valid password
- **THEN** the app stores the session and shows the Verify email screen for that email

#### Scenario: Short password is blocked

- **WHEN** the user enters a password shorter than 8 characters
- **THEN** an inline message is shown and the submit control is disabled

#### Scenario: Taken email is reported

- **WHEN** the user registers an email that already has an account
- **THEN** the screen stays open and says the email is already registered

#### Scenario: Referral code is optional and sent when entered

- **WHEN** the user enters a referral code along with a valid email and password and submits
- **THEN** the app sends the code with the registration
- **AND** after the user verifies their email, the home screen shows the bonus generations

#### Scenario: Unknown referral code is reported

- **WHEN** the user submits a referral code the server does not recognise
- **THEN** the screen stays open, says the code was not recognised, and keeps the entered email and password

## ADDED Requirements

### Requirement: Verify the email with a code

The app SHALL provide a Verify email screen that names the email the code was sent to and takes a 6-digit code. The submit control SHALL be disabled while the field does not hold exactly 6 digits and while a request is in flight. On success the app SHALL refresh the account and show the home screen. On failure it SHALL stay open and show the server's explanation.

#### Scenario: Correct code opens home

- **WHEN** the user enters the code from the email and submits
- **THEN** the home screen is shown and no longer shows the verification banner

#### Scenario: Wrong code is reported

- **WHEN** the user submits a wrong code
- **THEN** the screen stays open and says the code is incorrect

#### Scenario: Expired code suggests a new one

- **WHEN** the server answers that the code has expired
- **THEN** the screen says the code has expired and points the user to Resend

#### Scenario: Incomplete code cannot be submitted

- **WHEN** the code field holds fewer than 6 digits
- **THEN** the submit control is disabled

### Requirement: Resend the verification code

The Verify email screen SHALL offer a Resend action. Resend SHALL be disabled, with a visible countdown, for 60 seconds after the screen opens following registration and after each successful resend. When the server refuses because emails were sent too recently or too often, the screen SHALL say so.

#### Scenario: Resend starts a countdown

- **WHEN** the user taps Resend while it is enabled
- **THEN** the app asks the server for a new code
- **AND** Resend is disabled with a countdown for 60 seconds

#### Scenario: Server refusal is shown

- **WHEN** the server answers a resend with HTTP 429
- **THEN** the screen says too many codes were requested and to try again later

### Requirement: Postpone verification

The Verify email screen SHALL offer a Later action that shows the home screen without verifying.

#### Scenario: Later opens home unverified

- **WHEN** the user taps Later on the Verify email screen
- **THEN** the home screen is shown with the verification banner

### Requirement: Prompt unverified users on the home screen

While the signed-in account's email is not verified, the home screen SHALL show a banner saying the email must be verified before generating, and tapping it SHALL open the Verify email screen. The banner SHALL NOT be shown for a verified account or while the account is still loading.

#### Scenario: Unverified account sees the banner

- **WHEN** an unverified user opens the home screen
- **THEN** the verification banner is shown
- **AND** tapping it opens the Verify email screen

#### Scenario: Verified account sees no banner

- **WHEN** a verified user opens the home screen
- **THEN** no verification banner is shown

### Requirement: Open verification when a generation is refused

When the server refuses a generation because the email is not verified, the app SHALL open the Verify email screen. The selected photo and prompt SHALL be kept so the user can submit again after verifying.

#### Scenario: Unverified submit opens the Verify screen

- **WHEN** an unverified user submits a generation and the server answers with error `email_not_verified`
- **THEN** the Verify email screen is shown
- **AND** returning from it shows the same photo and prompt on the form

### Requirement: Request a password reset

The sign-in screen SHALL offer a Forgot password action that opens a screen taking an email address, prefilled with any email already typed on the sign-in screen. Submitting SHALL ask the server to send a reset code and then open the reset screen for that email. The app SHALL proceed in the same way whether or not the email has an account.

#### Scenario: Forgot password leads to the reset screen

- **WHEN** the user taps Forgot password, enters an email, and submits
- **THEN** the reset screen is shown, saying that if an account exists for that email a code was sent

#### Scenario: Malformed email is reported

- **WHEN** the user submits an email the server rejects as malformed
- **THEN** the screen stays open and says the email address is not valid

### Requirement: Reset the password with a code

The reset screen SHALL take the 6-digit code and a new password of at least 8 characters, with an inline message when the password is too short. On success the app SHALL store the returned session and show the home screen. On a rejected code it SHALL stay open, say the code is incorrect or expired, and keep the entered values. It SHALL offer Resend with the same 60-second countdown as the Verify email screen.

#### Scenario: Successful reset signs the user in

- **WHEN** the user enters the emailed code and a valid new password and submits
- **THEN** the home screen is shown as that user

#### Scenario: Rejected code keeps the values

- **WHEN** the user submits a wrong or expired code
- **THEN** the screen stays open, says the code is incorrect or has expired, and keeps the entered code and password

#### Scenario: Short new password is blocked

- **WHEN** the user enters a new password shorter than 8 characters
- **THEN** an inline message is shown and the submit control is disabled

