import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_errors.dart';
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

  /// Confirms the account's age and reloads it; an account the server already
  /// holds as confirmed counts as done. A refusal (`under_age`) throws.
  Future<void> confirmAge(DateTime dateOfBirth) async {
    final api = ref.read(apiClientProvider);
    try {
      await api.confirmAge(dateOfBirth: dateOfBirth);
    } on DioException catch (error) {
      if (!isAgeAlreadyConfirmed(error)) rethrow;
    }
    state = AsyncData(await api.fetchMe());
  }

  /// Records consent to the version the account last reported as current, then
  /// reloads it. A version that changed meanwhile throws `consent_version_mismatch`.
  Future<void> acceptConsent() async {
    final api = ref.read(apiClientProvider);
    final version = state.valueOrNull?.consent?.currentVersion;
    if (version == null) throw StateError('no consent version to accept');
    await api.acceptConsent(version: version);
    state = AsyncData(await api.fetchMe());
  }

  Future<void> withdrawConsent() async {
    final api = ref.read(apiClientProvider);
    await api.withdrawConsent();
    state = AsyncData(await api.fetchMe());
  }
}

final accountProvider =
    AsyncNotifierProvider<AccountNotifier, UserProfile?>(AccountNotifier.new);
