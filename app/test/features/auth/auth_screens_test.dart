import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/session.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;

Future<void> _enter(WidgetTester tester, String email, String password) async {
  await tester.enterText(find.widgetWithText(TextField, 'Email'), email);
  await tester.enterText(find.widgetWithText(TextField, 'Password'), password);
  await tester.pump();
}

bool _submitEnabled(WidgetTester tester, String label) =>
    tester.widget<FilledButton>(find.widgetWithText(FilledButton, label)).onPressed !=
    null;

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage();
  });

  group('sign in', () {
    testWidgets('successful sign-in stores the session and shows home', (tester) async {
      await pumpApp(tester, client: client, storage: storage);

      await _enter(tester, 'ana@example.com', 'password-1');
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pumpAndSettle();

      expect(find.text('Trending'), findsOneWidget);
      expect(client.loggedIn, ['ana@example.com']);
      expect(storage.saved?.email, 'ana@example.com');
    });

    testWidgets('wrong credentials show the server message and stay put', (tester) async {
      client.onLogin = (_, _) async => throw apiError(
            401,
            'invalid_credentials',
            'email or password is incorrect',
          );
      await pumpApp(tester, client: client, storage: storage);

      await _enter(tester, 'ana@example.com', 'wrong-password');
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pumpAndSettle();

      expect(find.text('email or password is incorrect'), findsOneWidget);
      expect(find.text('Trending'), findsNothing);
    });

    testWidgets('a throttled login shows the lockout message', (tester) async {
      client.onLogin = (_, _) async => throw apiError(
            429,
            'too_many_attempts',
            'too many failed attempts; try again in 15 minutes',
          );
      await pumpApp(tester, client: client, storage: storage);

      await _enter(tester, 'ana@example.com', 'password-1');
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pumpAndSettle();

      expect(find.textContaining('too many failed attempts'), findsOneWidget);
    });

    testWidgets('submit is disabled while blank and while a request is in flight', (tester) async {
      final pending = Completer<Session>();
      client.onLogin = (_, _) => pending.future;
      await pumpApp(tester, client: client, storage: storage);

      expect(_submitEnabled(tester, 'Sign in'), isFalse);
      await _enter(tester, 'ana@example.com', '');
      expect(_submitEnabled(tester, 'Sign in'), isFalse);

      await _enter(tester, 'ana@example.com', 'password-1');
      expect(_submitEnabled(tester, 'Sign in'), isTrue);

      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pump();
      expect(_submitEnabled(tester, 'Sign in'), isFalse);

      pending.complete(
        const Session(token: 't', userId: 'user-1', email: 'ana@example.com'),
      );
      await tester.pumpAndSettle();
    });
  });

  group('registration', () {
    Future<void> openRegister(WidgetTester tester) async {
      await pumpApp(tester, client: client, storage: storage);
      await tester.tap(find.text('Create an account'));
      await tester.pumpAndSettle();
    }

    testWidgets('registration shows the Confirm registration screen without a session', (tester) async {
      await openRegister(tester);

      await _enter(tester, 'new@example.com', 'password-1');
      await chooseDateOfBirth(tester);
      await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
      await tester.pumpAndSettle();

      expect(find.text('Confirm registration'), findsOneWidget);
      expect(find.textContaining('new@example.com'), findsOneWidget);
      expect(find.text('Trending'), findsNothing);
      expect(client.registered, ['new@example.com']);
      expect(storage.saved, isNull);
    });

    testWidgets('a short password shows an inline message and blocks submit', (tester) async {
      await openRegister(tester);

      await _enter(tester, 'new@example.com', 'short');

      expect(find.text('At least 8 characters'), findsOneWidget);
      expect(_submitEnabled(tester, 'Create account'), isFalse);
    });

    testWidgets('a taken email is reported', (tester) async {
      client.onRegister = (_, _) async => throw apiError(
            409,
            'email_taken',
            'this email is already registered',
          );
      await openRegister(tester);

      await _enter(tester, 'ana@example.com', 'password-1');
      await chooseDateOfBirth(tester);
      await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
      await tester.pumpAndSettle();

      expect(find.text('Email already registered'), findsOneWidget);
      expect(find.text('Confirm registration'), findsNothing);
      expect(find.text('Trending'), findsNothing);
    });

    testWidgets('links back to sign-in', (tester) async {
      await openRegister(tester);

      await tester.tap(find.text('I already have an account'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    });
  });
}
