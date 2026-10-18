## MODIFIED Requirements

### Requirement: Delete the account

The profile screen SHALL provide a Delete account action that explains the deletion is permanent and calls the server only after the user confirms. For an account with a password it SHALL ask for the password. For an account without a password it SHALL ask the user to sign in again with a linked provider and send that fresh sign-in as the confirmation. On success the app SHALL remove the local session and show the sign-in screen; on a wrong password or a rejected provider sign-in it SHALL stay on the profile screen and say so. When the user cancels the provider sign-in, the app SHALL stay on the profile screen without an error.

#### Scenario: Deleting the account signs the user out

- **WHEN** the user confirms deletion with the correct password
- **THEN** the sign-in screen is shown and the old session no longer works

#### Scenario: Wrong password keeps the account

- **WHEN** the user confirms deletion with a wrong password
- **THEN** the profile screen stays open with a message that the password is incorrect

#### Scenario: Provider-only account confirms with the provider

- **WHEN** a user whose account has no password and is linked to Google confirms deletion
- **THEN** the app asks the user to sign in with Google instead of asking for a password
- **AND** after a successful Google sign-in the sign-in screen is shown and the old session no longer works

#### Scenario: Cancelled provider sign-in keeps the account

- **WHEN** a provider-only user confirms deletion and then cancels the Google sign-in sheet
- **THEN** the profile screen stays open with no error and the account still works

## ADDED Requirements

### Requirement: Register with email and password

The app SHALL provide a registration screen reachable from the sign-in screen, taking an email, a password of at least 8 characters, and an optional referral code, with an inline message when the password is too short. On success the app SHALL show the Confirm registration screen for that email, without signing in; when the email is taken or the referral code is not recognised it SHALL say so and keep the entered values.

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

### Requirement: Confirm registration with the emailed code

The app SHALL provide a Confirm registration screen that names the email the code was sent to and takes a 6-digit code. The submit control SHALL be disabled while the field does not hold exactly 6 digits and while a request is in flight. On success the app SHALL store the returned session and show the home screen. A wrong code SHALL be reported as incorrect, and an expired code SHALL be reported as expired with a pointer to Resend. Resend SHALL send the registration again with the values the user entered, and SHALL be disabled with a visible countdown for 60 seconds after the screen opens and after each successful resend. A server refusal for sending too often SHALL be shown. Going back SHALL return to the registration screen with the entered values kept.

#### Scenario: Correct code signs in

- **WHEN** the user enters the emailed code and submits
- **THEN** the app stores the session and shows the home screen

#### Scenario: Wrong code is reported

- **WHEN** the user submits a wrong code
- **THEN** the screen stays open and says the code is incorrect

#### Scenario: Expired code points to Resend

- **WHEN** the server answers that the code has expired
- **THEN** the screen says the code has expired and points the user to Resend

#### Scenario: Resend starts a countdown

- **WHEN** the user taps Resend while it is enabled
- **THEN** the app sends the registration again
- **AND** Resend is disabled with a countdown for 60 seconds

#### Scenario: Email taken in the meantime

- **WHEN** the server answers the confirmation with error `email_taken`
- **THEN** the screen says the email is already registered and offers to go to sign-in

#### Scenario: Back keeps the entered values

- **WHEN** the user goes back from the Confirm registration screen
- **THEN** the registration screen shows the email, password, and referral code that were entered

### Requirement: Offer sign-in with Google and Apple

The sign-in and registration screens SHALL show a "Continue with Google" button on iOS and Android and a "Continue with Apple" button on iOS only. A button SHALL be hidden when the app has no client configuration for that provider. On success the app SHALL store the session and show the home screen, or the referral prompt when the server reports a new account. When the user cancels the provider sheet the app SHALL stay on the screen without an error. When the server rejects the sign-in the app SHALL show its explanation.

#### Scenario: Google sign-in opens home

- **WHEN** an existing user taps Continue with Google and completes the Google sheet
- **THEN** the app stores the session and shows the home screen

#### Scenario: Apple button only on iOS

- **WHEN** the sign-in screen is shown on Android
- **THEN** there is a Continue with Google button and no Continue with Apple button

#### Scenario: Unconfigured provider is hidden

- **WHEN** the app has no Google client configuration
- **THEN** no Continue with Google button is shown

#### Scenario: Cancelling shows no error

- **WHEN** the user taps Continue with Google and closes the Google sheet
- **THEN** the sign-in screen stays open with no error message

#### Scenario: Server rejection is shown

- **WHEN** the server rejects a Google sign-in because the Google email is not verified
- **THEN** the sign-in screen stays open and says the Google email must be verified first

#### Scenario: Rejection names the provider used

- **WHEN** the server rejects an Apple sign-in because the Apple email is not verified
- **THEN** the message names Apple, not Google

### Requirement: Prompt for a referral code after a provider sign-up

After a sign-in that created a new account through a provider, the app SHALL show a "Have a referral code?" screen with a code field, an Apply action, and a Skip action, before the home screen. Apply SHALL send the code and, on success, refresh the account and show the home screen. An unrecognised code SHALL be reported and keep the entered value. Skip SHALL show the home screen. The screen SHALL NOT be shown after a sign-in to an existing account.

#### Scenario: Applying a code rewards the new account

- **WHEN** a new Google user enters a friend's referral code and taps Apply
- **THEN** the home screen is shown with the bonus generations

#### Scenario: Unknown code is reported

- **WHEN** the user applies a code the server does not recognise
- **THEN** the screen stays open, says the code was not recognised, and keeps the entered code

#### Scenario: Skip goes home

- **WHEN** the user taps Skip
- **THEN** the home screen is shown and no code is sent

#### Scenario: Existing account is not prompted

- **WHEN** a user signs in with Google to an account that already existed
- **THEN** the home screen is shown without the referral prompt

### Requirement: Show linked sign-in providers on the profile

The profile screen SHALL show which providers the account is linked to, as "Signed in with Google" or "Signed in with Apple", and SHALL show nothing for an account with no linked provider.

#### Scenario: Google-linked account

- **WHEN** a user whose account is linked to Google opens the profile screen
- **THEN** the screen shows "Signed in with Google"

#### Scenario: Password-only account

- **WHEN** a user whose account has no linked provider opens the profile screen
- **THEN** no provider line is shown

## REMOVED Requirements

### Requirement: Create an account
**Reason**: Registration now leads to the Confirm registration screen and signs in only after the code is confirmed.
**Migration**: Replaced by "Register with email and password" and "Confirm registration with the emailed code".

### Requirement: Verify the email with a code
**Reason**: The code is now entered before the account exists, on the Confirm registration screen.
**Migration**: Use the Confirm registration screen. The Verify email screen and its route are removed.

### Requirement: Resend the verification code
**Reason**: Resend moved to the Confirm registration screen, where it sends the registration again.
**Migration**: See "Confirm registration with the emailed code".

### Requirement: Postpone verification
**Reason**: There is no signed-in unverified state to postpone into.
**Migration**: None. The user either confirms the code or goes back.

### Requirement: Prompt unverified users on the home screen
**Reason**: Every signed-in account is verified, so the banner can never show.
**Migration**: The banner is removed from the home screen.

### Requirement: Open verification when a generation is refused
**Reason**: The server no longer refuses generations for an unverified email.
**Migration**: The `email_not_verified` handling in the submit flow is removed.

