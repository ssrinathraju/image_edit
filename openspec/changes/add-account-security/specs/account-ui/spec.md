## ADDED Requirements

### Requirement: Show a sign-in and security section on the profile

The profile screen SHALL show a "Sign-in & security" section with:
- "Change password", or "Set a password" when the account has none;
- "Change email";
- a Google row, reading Linked or Not linked, with Link or Unlink;
- on iOS only, an Apple row with the same.

A provider row SHALL be hidden when that provider is not configured in the app.

#### Scenario: Password account

- **WHEN** a user with a password and no providers opens the profile
- **THEN** the section shows "Change password", "Change email", and Google with Link

#### Scenario: Provider-only account

- **WHEN** a user created through Google opens the profile
- **THEN** the section shows "Set a password" and Google with Unlink

### Requirement: Re-authenticate in the app before a change

Before sending a password change, an email change, or an unlink, the app SHALL ask the user to confirm it's them. An account with a password SHALL be asked for its current password. An account without one SHALL be asked to sign in again with a linked provider. A refusal (`reauth_failed`) SHALL say the password is incorrect or the sign-in couldn't be confirmed, and SHALL keep what was entered. Cancelling the provider sheet SHALL change nothing and show no error.

#### Scenario: Wrong current password

- **WHEN** the user enters a wrong current password while changing the email
- **THEN** the screen says the password is incorrect and keeps the new email entered

### Requirement: Change or set the password in the app

The Change password screen SHALL take a new password of at least 8 characters (with an inline message when shorter) and the re-authentication. On success it SHALL return to the profile and say the password was changed and other devices were signed out.

#### Scenario: Successful change

- **WHEN** the user enters a valid new password and the correct current password
- **THEN** the profile is shown with a message that the password was changed and other devices were signed out

### Requirement: Change the email in the app

The Change email screen SHALL take the new email and the re-authentication. It SHALL then show a code screen for the new address, with Resend (60-second countdown) and Back. A correct code SHALL return to the profile showing the new email and saying other devices were signed out. Taken-email, wrong-code and expired-code answers SHALL each be explained.

#### Scenario: Successful email change

- **WHEN** the user enters a new email, their password, and then the code from the new inbox
- **THEN** the profile shows the new email and says other devices were signed out

#### Scenario: Email already in use

- **WHEN** the server answers `email_taken`
- **THEN** the screen says that email is already used by another account and keeps the entered value

### Requirement: Link and unlink providers in the app

Link SHALL run the provider's sign-in sheet and link the result. Success SHALL show the row as Linked. `provider_in_use` SHALL say that account is already linked to a different user. Unlink SHALL ask for confirmation and re-authentication, and on success show the row as Not linked. `last_sign_in_method` SHALL say to set a password or link another provider first. Cancelling a sheet SHALL change nothing.

#### Scenario: Link Google

- **WHEN** the user taps Link on Google and completes the sheet
- **THEN** the Google row shows Linked

#### Scenario: Last sign-in method

- **WHEN** a provider-only user taps Unlink on their only provider and the server answers `last_sign_in_method`
- **THEN** the app says to set a password or link another provider first, and the row stays Linked
