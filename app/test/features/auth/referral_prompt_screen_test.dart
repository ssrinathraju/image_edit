import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/session.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;

final _apply = find.widgetWithText(FilledButton, 'Apply');
final _field = find.widgetWithText(TextField, 'Referral code');

Future<void> _openPrompt(WidgetTester tester) async {
  client.onSignInWithGoogle = (_) async => const ProviderSession(
        session: Session(token: 'token-g', userId: 'user-2', email: 'gina@example.com'),
        created: true,
      );
  await pumpApp(
    tester,
    client: client,
    storage: FakeSessionStorage(),
    google: FakeProviderSignIn.google(),
  );
  await tester.tap(find.text('Continue with Google'));
  await tester.pumpAndSettle();
  expect(find.text('Have a referral code?'), findsOneWidget);
}

void main() {
  setUp(() => client = FakeApiClient());

  testWidgets('Apply is disabled while the field is empty', (tester) async {
    await _openPrompt(tester);

    expect(tester.widget<FilledButton>(_apply).onPressed, isNull);

    await tester.enterText(_field, '   ');
    await tester.pump();
    expect(tester.widget<FilledButton>(_apply).onPressed, isNull);

    await tester.enterText(_field, 'K7M2QX9P');
    await tester.pump();
    expect(tester.widget<FilledButton>(_apply).onPressed, isNotNull);
  });

  testWidgets('Apply sends the trimmed code, refreshes the account and goes home', (
    tester,
  ) async {
    var fetches = 0;
    client.onFetchMe = () async {
      fetches++;
      return fakeProfile(bonusCredits: fetches > 1 ? 5 : 0);
    };
    await _openPrompt(tester);
    final before = fetches;

    await tester.enterText(_field, ' k7m2qx9p ');
    await tester.pump();
    await tester.tap(_apply);
    await tester.pumpAndSettle();

    expect(client.redeemedCodes, ['k7m2qx9p']);
    expect(fetches, greaterThan(before));
    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Have a referral code?'), findsNothing);
  });

  testWidgets('an unrecognised code is reported and the value is kept', (tester) async {
    client.onRedeemReferral = (_) async => throw apiError(
          400,
          'invalid_referral_code',
          'this referral code was not recognised',
        );
    await _openPrompt(tester);

    await tester.enterText(_field, 'NOSUCH22');
    await tester.pump();
    await tester.tap(_apply);
    await tester.pumpAndSettle();

    expect(find.text('Code not recognised'), findsOneWidget);
    expect(find.text('Have a referral code?'), findsOneWidget);
    expect(tester.widget<TextField>(_field).controller!.text, 'NOSUCH22');
  });

  testWidgets('referral_not_allowed says so and goes home', (tester) async {
    client.onRedeemReferral = (_) async => throw apiError(
          409,
          'referral_not_allowed',
          'not allowed',
        );
    await _openPrompt(tester);

    await tester.enterText(_field, 'K7M2QX9P');
    await tester.pump();
    await tester.tap(_apply);
    await tester.pumpAndSettle();

    expect(find.text("This account can't redeem a code"), findsOneWidget);
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('Apply shows a spinner and is disabled while the request runs', (
    tester,
  ) async {
    final pending = Completer<void>();
    client.onRedeemReferral = (_) => pending.future;
    await _openPrompt(tester);

    await tester.enterText(_field, 'K7M2QX9P');
    await tester.pump();
    await tester.tap(_apply);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed, isNull);

    pending.complete();
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('Skip goes home without sending a request', (tester) async {
    await _openPrompt(tester);

    await tester.tap(find.text('Skip'));
    await tester.pumpAndSettle();

    expect(client.redeemedCodes, isEmpty);
    expect(find.text('Trending'), findsOneWidget);
  });
}
