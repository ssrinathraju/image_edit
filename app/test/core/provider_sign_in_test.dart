import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:image_edit/core/provider_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

AuthorizationCredentialAppleID _appleCredential({String? identityToken = 'id-token'}) =>
    AuthorizationCredentialAppleID(
      userIdentifier: 'apple-user',
      givenName: null,
      familyName: null,
      authorizationCode: 'auth-code',
      email: null,
      identityToken: identityToken,
      state: null,
    );

void main() {
  group('Apple', () {
    test('the nonce is 32 random bytes and Apple receives their SHA-256', () async {
      String? received;
      final signIn = AppleProviderSignIn(
        random: Random(7),
        credentialSource: (hashed) async {
          received = hashed;
          return _appleCredential();
        },
      );

      final credential = (await signIn.signIn())!;

      final rawBytes = base64Url.decode(base64Url.normalize(credential.nonce!));
      expect(rawBytes, hasLength(32));
      expect(received, sha256.convert(utf8.encode(credential.nonce!)).toString());
      expect(received, isNot(credential.nonce));
      expect(credential.provider, SignInProvider.apple);
      expect(credential.token, 'id-token');
      expect(credential.authorizationCode, 'auth-code');
    });

    test('every sign-in uses a fresh nonce', () async {
      final signIn = AppleProviderSignIn(
        credentialSource: (_) async => _appleCredential(),
      );

      final first = await signIn.signIn();
      final second = await signIn.signIn();

      expect(first!.nonce, isNot(second!.nonce));
    });

    test('a cancelled sheet returns null', () async {
      final signIn = AppleProviderSignIn(
        credentialSource: (_) async => throw const SignInWithAppleAuthorizationException(
          code: AuthorizationErrorCode.canceled,
          message: 'cancelled',
        ),
      );

      expect(await signIn.signIn(), isNull);
    });

    test('other Apple failures are rethrown', () async {
      final signIn = AppleProviderSignIn(
        credentialSource: (_) async => throw const SignInWithAppleAuthorizationException(
          code: AuthorizationErrorCode.failed,
          message: 'failed',
        ),
      );

      expect(signIn.signIn(), throwsA(isA<SignInWithAppleAuthorizationException>()));
    });

    test('a credential without an identity token is an error', () async {
      final signIn = AppleProviderSignIn(
        credentialSource: (_) async => _appleCredential(identityToken: null),
      );

      expect(signIn.signIn(), throwsA(isA<StateError>()));
    });
  });

  group('Google', () {
    test('returns the ID token', () async {
      final signIn = GoogleProviderSignIn(tokenSource: () async => 'google-id-token');

      final credential = (await signIn.signIn())!;

      expect(credential.provider, SignInProvider.google);
      expect(credential.token, 'google-id-token');
      expect(credential.nonce, isNull);
    });

    test('a cancelled sheet returns null', () async {
      final signIn = GoogleProviderSignIn(
        tokenSource: () async => throw const GoogleSignInException(
          code: GoogleSignInExceptionCode.canceled,
        ),
      );

      expect(await signIn.signIn(), isNull);
    });

    test('other Google failures are rethrown', () async {
      final signIn = GoogleProviderSignIn(
        tokenSource: () async => throw const GoogleSignInException(
          code: GoogleSignInExceptionCode.clientConfigurationError,
        ),
      );

      expect(signIn.signIn(), throwsA(isA<GoogleSignInException>()));
    });
  });
}
