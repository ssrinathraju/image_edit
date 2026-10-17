import 'dart:async';

import 'package:image_edit/core/provider_sign_in.dart';

/// A provider sheet that returns [result] (null means cancelled), throws [error],
/// or waits for [gate] to complete first.
class FakeProviderSignIn implements ProviderSignIn {
  FakeProviderSignIn(this.result, {this.error, this.gate});

  /// A Google sheet that returns [token].
  FakeProviderSignIn.google([String token = 'google-id-token'])
      : result = ProviderCredential(provider: SignInProvider.google, token: token),
        error = null,
        gate = null;

  /// An Apple sheet that returns [token] with a raw nonce and code.
  FakeProviderSignIn.apple([String token = 'apple-id-token'])
      : result = ProviderCredential(
          provider: SignInProvider.apple,
          token: token,
          nonce: 'raw-nonce',
          authorizationCode: 'apple-code',
        ),
        error = null,
        gate = null;

  ProviderCredential? result;
  Object? error;
  Completer<void>? gate;
  var calls = 0;

  @override
  Future<ProviderCredential?> signIn() async {
    calls++;
    await gate?.future;
    if (error != null) throw error!;
    return result;
  }
}
