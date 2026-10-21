# account-ui Specification

## Purpose
The app's account experience: signing in and out, staying signed in across launches, and a profile screen where the user sees their account and manages it.

## Requirements

### Requirement: Require sign-in to use the app

The app SHALL show the sign-in screen whenever there is no valid session, except that on the first launch on a device it SHALL first show the onboarding pages described by the onboarding capability. It SHALL NOT show the home, template, custom, status, or profile screens until the user is signed in. While the app is restoring a saved session at launch it SHALL show a loading state rather than the sign-in screen.

#### Scenario: Signed-out launch shows sign-in

- **WHEN** the app launches with no saved session and onboarding has already been seen on this device
- **THEN** the sign-in screen is shown

#### Scenario: First launch shows onboarding before sign-in

- **WHEN** the app launches for the first time on a device with no saved session
- **THEN** the onboarding pages are shown
- **AND** finishing or skipping them shows the sign-in screen

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

### Requirement: Confirm registration with the emailed code

The app SHALL provide a Confirm registration screen that names the email the code was sent to and takes a 6-digit code. The submit control SHALL be disabled while the field does not hold exactly 6 digits and while a request is in flight. Confirming SHALL send the code together with the email and password the user registered with. On success the app SHALL store the returned session and show the home screen. A wrong code SHALL be reported as incorrect, and an expired code SHALL be reported as expired with a pointer to Resend. Resend SHALL send the registration again with the values the user entered, and SHALL be disabled with a visible countdown for 60 seconds after the screen opens and after each successful resend. A server refusal for sending too often SHALL be shown. Going back SHALL return to the registration screen with the entered values kept.

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

#### Scenario: Changed registration sends the user back to register

- **WHEN** the server answers the confirmation with error `registration_changed`
- **THEN** the app returns to the registration screen with the entered values kept
- **AND** says the registration changed and must be submitted again

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
