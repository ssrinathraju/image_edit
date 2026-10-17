# account-ui Specification

## Purpose
The app's account experience: signing in and out, staying signed in across launches, and a profile screen where the user sees their account and manages it.

## Requirements

### Requirement: Require sign-in to use the app

The app SHALL show the sign-in screen whenever there is no valid session and SHALL NOT show the home, template, custom, status, or profile screens until the user is signed in. While the app is restoring a saved session at launch it SHALL show a loading state rather than the sign-in screen.

#### Scenario: Signed-out launch shows sign-in

- **WHEN** the app launches with no saved session
- **THEN** the sign-in screen is shown

#### Scenario: Saved session is restored

- **WHEN** the app launches with a saved session that the server accepts
- **THEN** the home screen is shown without asking for credentials

### Requirement: Sign in

The sign-in screen SHALL let the user enter an email and password and submit them. It SHALL disable the submit control while a request is in flight and while either field is blank, SHALL show the server's explanation on failure (including the lockout message for too many attempts), and SHALL open the home screen on success.

#### Scenario: Successful sign-in opens home

- **WHEN** the user enters valid credentials and submits
- **THEN** the app stores the session and shows the home screen

#### Scenario: Wrong credentials show an error

- **WHEN** the user submits a wrong password
- **THEN** the sign-in screen stays open and shows that the email or password is incorrect

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

### Requirement: Return to sign-in when the session is invalid

When any request is answered with HTTP 401, the app SHALL discard the saved session, clear any remembered photo and prompt, and show the sign-in screen.

#### Scenario: Expired session returns to sign-in

- **WHEN** the server answers a request with HTTP 401 while the user is on any signed-in screen
- **THEN** the app shows the sign-in screen and the saved session is gone

### Requirement: Open the profile from the home screen

The home screen SHALL provide a control that opens the profile screen, and the profile screen SHALL provide a way back to the home screen.

#### Scenario: Profile is reachable and returnable

- **WHEN** the user taps the profile control on the home screen
- **THEN** the profile screen is shown
- **AND** the user can return to the home screen from it

### Requirement: Show account details on the profile screen

The profile screen SHALL show the signed-in user's email and an avatar made from its first letter, and the app version.

#### Scenario: Header shows the signed-in email

- **WHEN** a user signed in as `ana@example.com` opens the profile screen
- **THEN** the screen shows `ana@example.com` and the letter `A` as the avatar

### Requirement: Link to help and legal pages

The profile screen SHALL show Help and feedback, Privacy policy, and Terms entries that open the support email address and the privacy and terms pages configured for the app. An entry whose address is not configured SHALL NOT be shown.

#### Scenario: Configured links are shown

- **WHEN** a privacy policy URL and a support email are configured
- **THEN** the profile screen shows Privacy policy and Help and feedback entries
- **AND** tapping Privacy policy opens that URL

#### Scenario: Unconfigured links are hidden

- **WHEN** no terms URL is configured
- **THEN** the profile screen does not show a Terms entry

### Requirement: Log out

The profile screen SHALL provide a Log out action that revokes the session on the server, removes the saved session and any remembered photo and prompt from the device, and shows the sign-in screen. If the server cannot be reached the app SHALL still remove the local session and show the sign-in screen.

#### Scenario: Log out returns to sign-in

- **WHEN** the user taps Log out and confirms
- **THEN** the sign-in screen is shown
- **AND** relaunching the app shows the sign-in screen

#### Scenario: Log out works offline

- **WHEN** the user taps Log out while the server is unreachable
- **THEN** the local session is removed and the sign-in screen is shown

### Requirement: Delete the account

The profile screen SHALL provide a Delete account action that explains the deletion is permanent, asks for the password, and calls the server only after the user confirms. On success the app SHALL remove the local session and show the sign-in screen; on a wrong password it SHALL stay on the profile screen and say so.

#### Scenario: Deleting the account signs the user out

- **WHEN** the user confirms deletion with the correct password
- **THEN** the sign-in screen is shown and the old session no longer works

#### Scenario: Wrong password keeps the account

- **WHEN** the user confirms deletion with a wrong password
- **THEN** the profile screen stays open with a message that the password is incorrect

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
