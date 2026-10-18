## REMOVED Requirements

### Requirement: Require a verified email to generate
**Reason**: Accounts are created only after the registration code is confirmed or a provider vouches for the email, and older unverified accounts are marked verified on upgrade. An account with an unverified email can no longer exist, so the check could never fire.
**Migration**: `POST /generations` no longer returns 403 `email_not_verified`. Clients drop that handling.
