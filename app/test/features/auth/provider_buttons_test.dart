import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/session.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;

final _googleButton = find.widgetWithText(OutlinedButton, 'Continue with Google');
final _appleButton = find.byType(SignInWithAppleButton);

const _existing = ProviderSession(
  session: Session(token: 'token-g', userId: 'user-2', email: 'gina@example.com'),
  created: false,
);
const _created = ProviderSession(
  session: Session(token: 'token-g', userId: 'user-2', email: 'gina@example.com'),
  created: true,
);

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage();
    dotenv.testLoad(fileInput: '');
  });

  testWidgets('Google success stores the session and opens home', (tester) async {
    client.onSignInWithGoogle = (_) async => _existing;
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();

    expect(client.googleTokens, ['google-id-token']);
    expect(find.text('Trending'), findsOneWidget);
    expect(storage.saved!.token, 'token-g');
  });

  testWidgets('Apple sends the token, raw nonce and code', (tester) async {
    client.onSignInWithApple = (_, _, _) async => _existing;
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      apple: FakeProviderSignIn.apple(),
      platform: TargetPlatform.iOS,
    );

    await tester.tap(_appleButton);
    await tester.pumpAndSettle();

    expect(client.appleSignIns, [
      ['apple-id-token', 'raw-nonce', 'apple-code'],
    ]);
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('a new account opens the referral prompt', (tester) async {
    client.onSignInWithGoogle = (_) async => _created;
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();

    expect(find.text('Have a referral code?'), findsOneWidget);
  });

  testWidgets('the same buttons are on the register screen', (tester) async {
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();

    expect(_googleButton, findsOneWidget);
  });

  testWidgets('with no configuration no provider button is shown', (tester) async {
    await pumpApp(tester, client: client, storage: storage);

    expect(find.textContaining('Continue with'), findsNothing);
    expect(find.text('or'), findsNothing);
  });

  testWidgets('Google is hidden when it is not configured', (tester) async {
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      google: FakeProviderSignIn.google(),
      apple: FakeProviderSignIn.apple(),
      googleAvailable: false,
      appleAvailable: true,
    );

    expect(_googleButton, findsNothing);
    expect(_appleButton, findsOneWidget);
  });

  testWidgets('Apple is hidden on Android even when enabled', (tester) async {
    dotenv.testLoad(
      fileInput: 'GOOGLE_SERVER_CLIENT_ID=web.apps\nAPPLE_SIGN_IN=true\n',
    );
    await pumpApp(tester, client: client, storage: storage);

    expect(_googleButton, findsOneWidget);
    expect(_appleButton, findsNothing);
  });

  testWidgets('Apple is shown on iOS when enabled', (tester) async {
    dotenv.testLoad(
      fileInput: 'GOOGLE_SERVER_CLIENT_ID=web.apps\nGOOGLE_IOS_CLIENT_ID=ios.apps\n'
          'APPLE_SIGN_IN=true\n',
    );
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      platform: TargetPlatform.iOS,
    );

    expect(_googleButton, findsOneWidget);
    expect(_appleButton, findsOneWidget);
  });

  testWidgets('Apple stays hidden on iOS when it is not enabled', (tester) async {
    dotenv.testLoad(
      fileInput: 'GOOGLE_SERVER_CLIENT_ID=web.apps\nGOOGLE_IOS_CLIENT_ID=ios.apps\n',
    );
    await pumpApp(tester, client: client, storage: storage, platform: TargetPlatform.iOS);

    expect(_googleButton, findsOneWidget);
    expect(_appleButton, findsNothing);
  });

  testWidgets('cancelling shows nothing and stays on sign-in', (tester) async {
    final cancelled = FakeProviderSignIn(null);
    await pumpApp(tester, client: client, storage: storage, google: cancelled);

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();

    expect(cancelled.calls, 1);
    expect(client.googleTokens, isEmpty);
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(find.textContaining('failed'), findsNothing);
    expect(find.textContaining('unavailable'), findsNothing);
  });

  const failures = <(String, int, String)>[
    ('invalid_provider_token', 401, 'Sign-in failed, try again'),
    ('provider_email_unverified', 400, 'Verify your Google email first'),
    (
      'provider_email_missing',
      400,
      "Apple didn't share an email; remove this app in Apple ID settings and try again",
    ),
    (
      'provider_already_linked',
      409,
      'This account is already linked to another Google account',
    ),
    ('provider_unavailable', 503, 'Sign-in is unavailable right now'),
    ('provider_not_configured', 503, 'Sign-in is unavailable right now'),
  ];
  for (final (code, status, message) in failures) {
    testWidgets('$code shows "$message"', (tester) async {
      client.onSignInWithGoogle = (_) async =>
          throw apiError(status, code, 'server wording');
      await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

      await tester.tap(_googleButton);
      await tester.pumpAndSettle();

      expect(find.text(message), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
      expect(storage.saved, isNull);
    });
  }

  testWidgets('an unverified Apple email names Apple, not Google', (tester) async {
    client.onSignInWithApple = (_, _, _) async =>
        throw apiError(400, 'provider_email_unverified', 'server wording');
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      apple: FakeProviderSignIn.apple(),
      platform: TargetPlatform.iOS,
    );

    await tester.tap(_appleButton);
    await tester.pumpAndSettle();

    expect(find.text('Verify your Apple email first'), findsOneWidget);
    expect(find.textContaining('Google'), findsNothing);
  });

  testWidgets('the Apple button follows Apple\'s style and wording', (tester) async {
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      apple: FakeProviderSignIn.apple(),
      platform: TargetPlatform.iOS,
    );

    final button = tester.widget<SignInWithAppleButton>(_appleButton);
    expect(button.text, 'Continue with Apple');
    expect(button.style, SignInWithAppleButtonStyle.black);
    expect(find.text('Continue with Apple'), findsOneWidget);
  });

  testWidgets('an unexpected failure shows the generic message', (tester) async {
    client.onSignInWithGoogle = (_) async => throw StateError('offline');
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();

    expect(find.text('Something went wrong. Please try again.'), findsOneWidget);
  });

  testWidgets('while in flight the button shows a spinner and the form is locked', (
    tester,
  ) async {
    final gate = Completer<void>();
    final google = FakeProviderSignIn.google()..gate = gate;
    client.onSignInWithGoogle = (_) async => _existing;
    await pumpApp(tester, client: client, storage: storage, google: google);
    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'ana@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
    await tester.pump();
    expect(
      tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Sign in')).onPressed,
      isNotNull,
    );

    await tester.tap(_googleButton);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(
      tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Sign in')).onPressed,
      isNull,
    );

    gate.complete();
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });
}
