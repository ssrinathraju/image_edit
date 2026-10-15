import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../schemas/session.dart';
import '../../services/generation_providers.dart';
import '../auth/session_notifier.dart';

/// The signed-in user's plan, usage and referral progress from `GET /me`.
/// `null` data means signed out; it is rebuilt whenever the session changes.
class AccountNotifier extends AsyncNotifier<UserProfile?> {
  @override
  Future<UserProfile?> build() async {
    final session = ref.watch(sessionProvider).valueOrNull;
    if (session == null) return null;
    return ref.read(apiClientProvider).fetchMe();
  }

  /// Reloads the account. A failed reload keeps what is already shown.
  Future<void> refresh() async {
    if (ref.read(sessionProvider).valueOrNull == null) return;
    final result = await AsyncValue.guard(ref.read(apiClientProvider).fetchMe);
    if (result.hasError) return;
    state = result;
  }
}

final accountProvider =
    AsyncNotifierProvider<AccountNotifier, UserProfile?>(AccountNotifier.new);
