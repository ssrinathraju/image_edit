## MODIFIED Requirements

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

