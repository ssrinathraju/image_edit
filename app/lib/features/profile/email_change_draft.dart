import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/reauth.dart';

/// The pending email change, held so Resend can ask for another code without
/// confirming the user's identity a second time.
class EmailChangeDraft {
  const EmailChangeDraft({required this.newEmail, required this.reauth});

  final String newEmail;
  final Reauth reauth;
}

/// In memory only, never persisted: it exists while the code screen is open.
final emailChangeDraftProvider = StateProvider<EmailChangeDraft?>((_) => null);
