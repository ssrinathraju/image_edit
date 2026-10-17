import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/provider_sign_in.dart';
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
  bool _justRegistered = false;

  /// True between registering and the Verify email screen opening, so the
  /// router can send a new account there instead of home.
  bool get justRegistered => _justRegistered;

  /// Reads and clears [justRegistered]; the Verify screen calls it when it opens.
  bool takeJustRegistered() {
    final value = _justRegistered;
    _justRegistered = false;
    return value;
  }

  bool _justCreatedViaProvider = false;

  /// True between a provider sign-in that created the account and the
  /// referral prompt opening, so the router can send the user there.
  bool get justCreatedViaProvider => _justCreatedViaProvider;

  /// Reads and clears [justCreatedViaProvider]; the prompt calls it when it opens.
  bool takeJustCreatedViaProvider() {
    final value = _justCreatedViaProvider;
    _justCreatedViaProvider = false;
    return value;
  }

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
      // Returning is what sets state here; build must not assign it.
      await _discardStoredSession();
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

  Future<void> register({
    required String email,
    required String password,
    String? referralCode,
  }) async {
    final session = await ref.read(apiClientProvider).register(
          email: email,
          password: password,
          referralCode: referralCode,
        );
    _justRegistered = true;
    await _start(session);
  }

  /// Signs in with what a Google or Apple sheet returned; the server links,
  /// finds or creates the account.
  Future<void> signInWithProvider(ProviderCredential credential) async {
    final api = ref.read(apiClientProvider);
    final result = switch (credential.provider) {
      SignInProvider.google => await api.signInWithGoogle(
          idToken: credential.token,
        ),
      SignInProvider.apple => await api.signInWithApple(
          identityToken: credential.token,
          nonce: credential.nonce!,
          authorizationCode: credential.authorizationCode ?? '',
        ),
    };
    _justCreatedViaProvider = result.created;
    await _start(result.session);
  }

  /// Sets a new password with an emailed code and signs in with the fresh
  /// session; a rejected code throws and leaves the user signed out.
  Future<void> completePasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    final session = await ref.read(apiClientProvider).confirmPasswordReset(
          email: email,
          code: code,
          newPassword: newPassword,
        );
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

  /// Deletes the account confirmed by a fresh provider sign-in; a rejected
  /// token throws and keeps the session.
  Future<void> deleteAccountWithProvider(ProviderCredential credential) async {
    await ref.read(apiClientProvider).deleteAccount(
          provider: credential.provider.apiName,
          token: credential.token,
          nonce: credential.nonce,
        );
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

  Future<void> _discardStoredSession() async {
    ref.read(sessionTokenHolderProvider).token = null;
    await ref.read(sessionStorageProvider).clear();
  }

  Future<void> _clearLocalSession() async {
    ref.invalidate(lastRequestProvider);
    ref.invalidate(homeNotifierProvider);
    _justCreatedViaProvider = false;
    await _discardStoredSession();
    state = const AsyncData(null);
  }
}

final sessionProvider =
    AsyncNotifierProvider<SessionNotifier, Session?>(SessionNotifier.new);
