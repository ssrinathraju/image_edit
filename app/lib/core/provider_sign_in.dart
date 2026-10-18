import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import '../configs/app_config.dart';

const int _nonceBytes = 32;

enum SignInProvider {
  google('google', 'Google'),
  apple('apple', 'Apple');

  const SignInProvider(this.apiName, this.label);

  /// The name the server uses in requests and in `/me`'s `providers`.
  final String apiName;
  final String label;
}

/// What a provider's sheet returned, ready to send to the server. [nonce] and
/// [authorizationCode] are set for Apple only; [nonce] is the raw value.
class ProviderCredential {
  const ProviderCredential({
    required this.provider,
    required this.token,
    this.nonce,
    this.authorizationCode,
  });

  final SignInProvider provider;
  final String token;
  final String? nonce;
  final String? authorizationCode;
}

abstract class ProviderSignIn {
  /// Shows the provider's sheet; null when the user cancels it.
  Future<ProviderCredential?> signIn();
}

/// Returns a Google ID token; throws [GoogleSignInException] on failure or cancel.
typedef GoogleIdTokenSource = Future<String> Function();

/// Asks Apple for a credential with [hashedNonce] embedded in its token.
typedef AppleCredentialSource = Future<AuthorizationCredentialAppleID> Function(
  String hashedNonce,
);

class GoogleProviderSignIn implements ProviderSignIn {
  GoogleProviderSignIn({GoogleIdTokenSource? tokenSource})
      : _tokenSource = tokenSource ?? _authenticateWithGoogle;

  final GoogleIdTokenSource _tokenSource;

  @override
  Future<ProviderCredential?> signIn() async {
    try {
      final idToken = await _tokenSource();
      return ProviderCredential(provider: SignInProvider.google, token: idToken);
    } on GoogleSignInException catch (error) {
      if (error.code == GoogleSignInExceptionCode.canceled) return null;
      rethrow;
    }
  }
}

bool _googleInitialized = false;

Future<String> _authenticateWithGoogle() async {
  final google = GoogleSignIn.instance;
  if (!_googleInitialized) {
    await google.initialize(
      clientId: defaultTargetPlatform == TargetPlatform.iOS
          ? AppConfig.googleIosClientId
          : null,
      serverClientId: AppConfig.googleServerClientId,
    );
    _googleInitialized = true;
  }
  final account = await google.authenticate();
  final idToken = account.authentication.idToken;
  if (idToken == null) {
    throw StateError('Google returned no ID token');
  }
  return idToken;
}

class AppleProviderSignIn implements ProviderSignIn {
  AppleProviderSignIn({AppleCredentialSource? credentialSource, Random? random})
      : _credentialSource = credentialSource ?? _requestAppleCredential,
        _random = random ?? Random.secure();

  final AppleCredentialSource _credentialSource;
  final Random _random;

  @override
  Future<ProviderCredential?> signIn() async {
    final rawNonce = _newRawNonce();
    final hashedNonce = sha256.convert(utf8.encode(rawNonce)).toString();
    try {
      final credential = await _credentialSource(hashedNonce);
      final identityToken = credential.identityToken;
      if (identityToken == null) {
        throw StateError('Apple returned no identity token');
      }
      return ProviderCredential(
        provider: SignInProvider.apple,
        token: identityToken,
        nonce: rawNonce,
        authorizationCode: credential.authorizationCode,
      );
    } on SignInWithAppleAuthorizationException catch (error) {
      if (error.code == AuthorizationErrorCode.canceled) return null;
      rethrow;
    }
  }

  String _newRawNonce() {
    final bytes = List<int>.generate(_nonceBytes, (_) => _random.nextInt(256));
    return base64UrlEncode(bytes).replaceAll('=', '');
  }
}

Future<AuthorizationCredentialAppleID> _requestAppleCredential(
  String hashedNonce,
) =>
    SignInWithApple.getAppleIDCredential(
      scopes: [AppleIDAuthorizationScopes.email],
      nonce: hashedNonce,
    );

final googleProviderSignInProvider =
    Provider<ProviderSignIn>((_) => GoogleProviderSignIn());

final appleProviderSignInProvider =
    Provider<ProviderSignIn>((_) => AppleProviderSignIn());

final targetPlatformProvider =
    Provider<TargetPlatform>((_) => defaultTargetPlatform);

/// Whether the Continue with Google button is shown.
final isGoogleSignInAvailableProvider = Provider<bool>(
  (ref) => AppConfig.isGoogleSignInAvailable(ref.watch(targetPlatformProvider)),
);

/// Whether the Continue with Apple button is shown.
final isAppleSignInAvailableProvider = Provider<bool>(
  (ref) => AppConfig.isAppleSignInAvailable(ref.watch(targetPlatformProvider)),
);

Provider<ProviderSignIn> signInProviderFor(SignInProvider provider) =>
    switch (provider) {
      SignInProvider.google => googleProviderSignInProvider,
      SignInProvider.apple => appleProviderSignInProvider,
    };
