import 'package:flutter_riverpod/flutter_riverpod.dart';

/// What the user typed while registering, held so Resend can send the
/// registration again without asking for the password a second time.
class RegistrationDraft {
  const RegistrationDraft({
    required this.email,
    required this.password,
    required this.dateOfBirth,
    this.referralCode,
  });

  final String email;
  final String password;

  /// Kept only so Resend can send the registration again; it dies with the draft.
  final DateTime dateOfBirth;
  final String? referralCode;
}

/// In memory only, never persisted: it exists while the Confirm registration
/// screen is open and is cleared when the account is created.
final registrationDraftProvider = StateProvider<RegistrationDraft?>((_) => null);
