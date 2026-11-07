## ADDED Requirements

### Requirement: Explain refused sign-ups

The app SHALL show "Use a permanent email address." when registration or an email change is refused with `disposable_email`, keeping what the user typed. When registration or a sign-in with Google or Apple is refused with `too_many_signups`, it SHALL say "Too many new accounts from this network. Try again in <time>.", with the wait taken from `Retry-After` and shown in minutes when it is a minute or more, and SHALL keep what the user typed.

#### Scenario: Disposable address on the register screen

- **WHEN** the user registers with a disposable address
- **THEN** the register screen shows "Use a permanent email address." and keeps the email, password and date of birth

#### Scenario: Too many sign-ups on the register screen

- **WHEN** registration is refused with `too_many_signups` and `Retry-After: 1800`
- **THEN** the screen says "Too many new accounts from this network. Try again in 30 minutes."

#### Scenario: Too many sign-ups with Google

- **WHEN** a Google sign-in that would create an account is refused with `too_many_signups`
- **THEN** the sign-in screen shows the same message and the user stays signed out

#### Scenario: Disposable address on the change email screen

- **WHEN** the user requests an email change to a disposable address
- **THEN** the change email screen shows "Use a permanent email address."
