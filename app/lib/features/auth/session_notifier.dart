import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/session_storage.dart';
import '../../schemas/session.dart';
import '../../services/generation_providers.dart';
import '../common/submit_controller.dart';
import '../home/home_notifier.dart';

final sessionStorageProvider =
    Provider<SessionStorage>((_) => SecureSessionStorage());

/// The bearer token the API client sends. A plain holder rather than provider
/// state: the notifier sets it while it is still building, which provider
/// state may not do.
class SessionTokenHolder {
  String? token;
}

final sessionTokenHolderProvider =
    Provider<SessionTokenHolder>((_) => SessionTokenHolder());

/// The signed-in session; `null` data means signed out, loading means the
/// saved session is being checked, and an error means it could not be checked.
class SessionNotifier extends AsyncNotifier<Session?> {
  bool _restoring = false;

  @override
  Future<Session?> build() async {
    final saved = await ref.read(sessionStorageProvider).read();
    if (saved == null) return null;

    ref.read(sessionTokenHolderProvider).token = saved.token;
    _restoring = true;
    try {
      final me = await ref.read(apiClientProvider).fetchMe();
      return Session(token: saved.token, userId: me.id, email: me.email);
    } on DioException catch (error) {
      if (error.response?.statusCode != 401) rethrow;
      await _clearLocalSession();
      return null;
    } finally {
      _restoring = false;
    }
  }

  /// Checks the saved session again after a network failure.
  void retryRestore() => ref.invalidateSelf();

  Future<void> signIn({required String email, required String password}) async {
    final session = await ref
        .read(apiClientProvider)
        .login(email: email, password: password);
    await _start(session);
  }

  Future<void> register({required String email, required String password}) async {
    final session = await ref
        .read(apiClientProvider)
        .register(email: email, password: password);
    await _start(session);
  }

  /// Ends the session; the local one is removed even if the server call fails.
  Future<void> signOut() async {
    try {
      await ref.read(apiClientProvider).logout();
    } on Object {
      // Offline or already revoked: the device must still sign out.
    }
    await _clearLocalSession();
  }

  /// Deletes the account; a wrong password throws and keeps the session.
  Future<void> deleteAccount({required String password}) async {
    await ref.read(apiClientProvider).deleteAccount(password: password);
    await _clearLocalSession();
  }

  /// Drops a session the server no longer accepts, without calling the server.
  Future<void> expire() async {
    if (_restoring) return;
    await _clearLocalSession();
  }

  Future<void> _start(Session session) async {
    await ref.read(sessionStorageProvider).write(session);
    ref.read(sessionTokenHolderProvider).token = session.token;
    state = AsyncData(session);
  }

  Future<void> _clearLocalSession() async {
    ref.read(sessionTokenHolderProvider).token = null;
    ref.invalidate(lastRequestProvider);
    ref.invalidate(homeNotifierProvider);
    await ref.read(sessionStorageProvider).clear();
    state = const AsyncData(null);
  }
}

final sessionProvider =
    AsyncNotifierProvider<SessionNotifier, Session?>(SessionNotifier.new);
