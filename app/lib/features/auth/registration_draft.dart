import 'package:flutter_riverpod/flutter_riverpod.dart';

/// What the user typed while registering, held so Resend can send the
/// registration again without asking for the password a second time.
class RegistrationDraft {
  const RegistrationDraft({
    required this.email,
    required this.password,
    this.referralCode,
  });

  final String email;
  final String password;
  final String? referralCode;
}

/// In memory only, never persisted: it exists while the Confirm registration
/// screen is open and is cleared when the account is created.
final registrationDraftProvider = StateProvider<RegistrationDraft?>((_) => null);
