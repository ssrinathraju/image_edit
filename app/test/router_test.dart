import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/schemas/session.dart';

import 'support/app_harness.dart';
import 'support/fake_api_client.dart';
import 'support/fake_session_storage.dart';

void main() {
  late FakeApiClient client;

  setUp(() => client = FakeApiClient());

  testWidgets('a signed-out launch lands on sign-in', (tester) async {
    await pumpApp(tester, client: client, storage: FakeSessionStorage());

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(find.text('Trending'), findsNothing);
  });

  testWidgets('a saved session is restored straight to home', (tester) async {
    await pumpApp(tester, client: client, storage: FakeSessionStorage(savedSession));

    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Sign in'), findsNothing);
  });

  testWidgets('a loading state is shown while the saved session is checked', (tester) async {
    final pending = Completer<UserProfile>();
    client.onFetchMe = () => pending.future;
    await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
      settle: false,
    );
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Sign in'), findsNothing);

    pending.complete(const UserProfile(id: 'user-1', email: 'ana@example.com'));
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('an unreachable server offers Retry instead of signing out', (tester) async {
    var calls = 0;
    client.onFetchMe = () async {
      calls++;
      if (calls == 1) {
        throw DioException(
          requestOptions: RequestOptions(path: '/me'),
          type: DioExceptionType.connectionError,
        );
      }
      return const UserProfile(id: 'user-1', email: 'ana@example.com');
    };
    final storage = FakeSessionStorage(savedSession);
    await pumpApp(tester, client: client, storage: storage);

    expect(find.text('Could not reach the server.'), findsOneWidget);
    expect(storage.saved, savedSession);

    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('an expired session on a signed-in screen returns to sign-in', (tester) async {
    final storage = FakeSessionStorage(savedSession);
    final container = await pumpApp(tester, client: client, storage: storage);
    expect(find.text('Trending'), findsOneWidget);

    await container.read(sessionProvider.notifier).expire();
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(storage.saved, isNull);
  });

  testWidgets('a signed-in user is redirected away from sign-in', (tester) async {
    final container = await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
    );

    container.read(routerProvider).go('/login');
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('a signed-out user cannot open the profile', (tester) async {
    final container = await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(),
    );

    container.read(routerProvider).go('/profile');
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
  });
}
