# Spec Delta

## Purpose

The app's account experience: signing in and out, staying signed in across launches, and a profile screen where the user sees their account and manages it.

## ADDED Requirements

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

The app SHALL provide a registration screen reachable from the sign-in screen, taking an email and a password of at least 8 characters, with an inline message when the password is too short. On success the app SHALL sign the user in and show the home screen; when the email is taken it SHALL say so.

#### Scenario: Registration signs the user in

- **WHEN** the user submits a new email and a valid password
- **THEN** the app shows the home screen as that user

#### Scenario: Short password is blocked

- **WHEN** the user enters a password shorter than 8 characters
- **THEN** an inline message is shown and the submit control is disabled

#### Scenario: Taken email is reported

- **WHEN** the user registers an email that already has an account
- **THEN** the screen stays open and says the email is already registered

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
