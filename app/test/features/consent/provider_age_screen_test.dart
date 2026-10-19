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

const _signedIn = ProviderSession(
  session: Session(token: 'token-g', userId: 'user-2', email: 'gina@example.com'),
  created: false,
);

Future<void> _failFirstWithAgeRequired(
  Future<ProviderSession> Function() secondCall,
  void Function(Future<ProviderSession> Function() handler) install,
) async {
  var calls = 0;
  install(() async {
    calls++;
    if (calls == 1) {
      throw apiError(400, 'age_required', 'send a date_of_birth');
    }
    return secondCall();
  });
}

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage();
    dotenv.testLoad(fileInput: '');
  });

  testWidgets('a new Google user is asked for a date of birth and then signed in', (tester) async {
    await _failFirstWithAgeRequired(
      () async => _signedIn,
      (handler) => client.onSignInWithGoogle = (_) => handler(),
    );
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      google: FakeProviderSignIn.google(),
      birthDate: DateTime(2000, 5, 6),
    );

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();
    expect(find.text('Your date of birth'), findsOneWidget);
    expect(
      tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Continue')).onPressed,
      isNull,
    );

    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Continue'));
    await tester.pumpAndSettle();

    expect(client.googleTokens, ['google-id-token', 'google-id-token']);
    expect(client.googleDates, [null, DateTime(2000, 5, 6)]);
    expect(find.text('Trending'), findsOneWidget);
    expect(storage.saved!.token, 'token-g');
  });

  testWidgets('Apple resends the same identity token, nonce and code', (tester) async {
    await _failFirstWithAgeRequired(
      () async => _signedIn,
      (handler) => client.onSignInWithApple = (_, _, _) => handler(),
    );
    final apple = FakeProviderSignIn.apple();
    await pumpApp(
      tester,
      client: client,
      storage: storage,
      apple: apple,
      platform: TargetPlatform.iOS,
    );

    await tester.tap(_appleButton);
    await tester.pumpAndSettle();
    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Continue'));
    await tester.pumpAndSettle();

    expect(client.appleSignIns, [
      ['apple-id-token', 'raw-nonce', 'apple-code'],
      ['apple-id-token', 'raw-nonce', 'apple-code'],
    ]);
    expect(client.appleDates, [null, defaultBirthDate]);
    expect(apple.calls, 1);
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('under_age returns to sign-in with the message and no session', (tester) async {
    var calls = 0;
    client.onSignInWithGoogle = (_) async {
      calls++;
      throw apiError(
        400,
        calls == 1 ? 'age_required' : 'under_age',
        'x',
      );
    };
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();
    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Continue'));
    await tester.pumpAndSettle();

    expect(find.text('You must be 18 or older to use this app'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(find.text('Your date of birth'), findsNothing);
    expect(storage.saved, isNull);
  });

  testWidgets('cancelling returns to sign-in with no session', (tester) async {
    client.onSignInWithGoogle = (_) async =>
        throw apiError(400, 'age_required', 'send a date_of_birth');
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(find.text('You must be 18 or older to use this app'), findsNothing);
    expect(storage.saved, isNull);
    expect(client.googleTokens, ['google-id-token']);
  });

  testWidgets('an expired token on the second try shows the existing message and stays', (tester) async {
    var calls = 0;
    client.onSignInWithGoogle = (_) async {
      calls++;
      throw apiError(
        calls == 1 ? 400 : 401,
        calls == 1 ? 'age_required' : 'invalid_provider_token',
        'x',
      );
    };
    await pumpApp(tester, client: client, storage: storage, google: FakeProviderSignIn.google());

    await tester.tap(_googleButton);
    await tester.pumpAndSettle();
    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Continue'));
    await tester.pumpAndSettle();

    expect(find.text('Sign-in failed, try again'), findsOneWidget);
    expect(find.text('Your date of birth'), findsOneWidget);
    expect(storage.saved, isNull);
  });
}
