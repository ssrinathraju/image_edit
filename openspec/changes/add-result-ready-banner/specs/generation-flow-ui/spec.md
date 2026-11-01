## ADDED Requirements

### Requirement: Tell the user when a result is ready on another screen

When the app saves a creation through the catch-up (not from that generation's own status screen) while the app is in the foreground and the same account is signed in, the app SHALL show a banner at the bottom of the current screen reading "Your image is ready" with a View action. The banner SHALL stay for 4 seconds unless dismissed or tapped. View SHALL open that creation's detail in My creations, on top of the current screen, so Back returns to where the user was.

The banner SHALL NOT be shown:
- when the screen in front is the status screen of that same generation;
- for a generation that failed, was blocked, or that the server no longer knows;
- after the account that submitted the generation has signed out.

When several results become ready close together, each SHALL get its own banner, shown one after another in the order they were saved.

#### Scenario: Result ready while on the home screen

- **WHEN** a user submits a generation, goes back to the home screen, and the result is saved by the catch-up
- **THEN** a banner reading "Your image is ready" with View is shown on the home screen

#### Scenario: View opens the creation

- **WHEN** the user taps View on the banner
- **THEN** the creation's detail screen opens showing that image
- **AND** Back returns to the screen the user was on

#### Scenario: Banner goes away on its own

- **WHEN** the banner is shown and the user does nothing
- **THEN** it is no longer shown after 4 seconds and the creation is still in My creations

#### Scenario: No banner on the generation's own status screen

- **WHEN** the user is still on the status screen of the generation when it succeeds
- **THEN** no banner is shown and the result is shown on the status screen as before

#### Scenario: Banner on another generation's status screen

- **WHEN** the user is on the status screen of generation B when generation A's result is saved
- **THEN** the banner for A is shown

#### Scenario: Failed generation shows no banner

- **WHEN** a remembered generation fails or is blocked while the user is on another screen
- **THEN** no banner is shown

#### Scenario: Two results ready together

- **WHEN** two remembered generations are saved in the same catch-up
- **THEN** two banners are shown one after the other, the first saved first

#### Scenario: Signed out before the banner

- **WHEN** a result is saved for an account that has since signed out
- **THEN** no banner is shown
