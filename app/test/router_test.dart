import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/provider_sign_in.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/schemas/session.dart';

import 'support/app_harness.dart';
import 'support/fake_api_client.dart';
import 'support/fake_image_picker.dart';
import 'support/fake_provider_sign_in.dart';
import 'support/in_memory_creation_store.dart';
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

  testWidgets('Upgrade and Invite friends are reachable from the profile', (tester) async {
    client.onFetchMe = () async => fakeProfile(usedToday: 1);
    await pumpApp(tester, client: client, storage: FakeSessionStorage(savedSession));

    await tester.tap(find.byTooltip('Profile'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Upgrade'));
    await tester.pumpAndSettle();
    expect(find.text('Payments are not available yet'), findsOneWidget);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Invite friends'));
    await tester.pumpAndSettle();
    expect(find.text('K7M2QX9P'), findsOneWidget);
  });

  testWidgets('registration lands on Confirm registration with no session', (tester) async {
    final storage = FakeSessionStorage();
    await pumpApp(tester, client: client, storage: storage);

    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    expect(find.text('Confirm registration'), findsOneWidget);
    expect(find.text('Trending'), findsNothing);
    expect(storage.saved, isNull);
  });

  testWidgets('confirming the code creates the session and lands on home', (tester) async {
    final storage = FakeSessionStorage();
    await pumpApp(tester, client: client, storage: storage);
    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextField, 'Code'), '123456');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Confirm registration'), findsNothing);
    expect(storage.saved?.email, 'new@example.com');
  });

  testWidgets('signing in lands on home, not the Confirm registration screen', (tester) async {
    await pumpApp(tester, client: client, storage: FakeSessionStorage());

    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'ana@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Confirm registration'), findsNothing);
  });

  testWidgets('a signed-out user may open the forgot and reset password pages', (tester) async {
    final container = await pumpApp(tester, client: client, storage: FakeSessionStorage());

    container.read(routerProvider).go('/forgot-password');
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Send code'), findsOneWidget);

    container.read(routerProvider).go('/reset-password?email=ana%40example.com');
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Reset password'), findsOneWidget);
    expect(find.textContaining('ana@example.com'), findsOneWidget);
  });

  testWidgets('Confirm registration without a draft redirects to the registration screen', (tester) async {
    final container = await pumpApp(tester, client: client, storage: FakeSessionStorage());

    container.read(routerProvider).go('/confirm-registration');
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Create account'), findsOneWidget);
    expect(find.text('Confirm registration'), findsNothing);
  });

  testWidgets('the removed Verify email page is not reachable', (tester) async {
    final container = await pumpApp(tester, client: client, storage: FakeSessionStorage());

    container.read(routerProvider).go('/verify-email');
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
  });

  testWidgets('a signed-in user opening the reset page is sent home', (tester) async {
    final container = await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
    );

    container.read(routerProvider).go('/reset-password?email=ana%40example.com');
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
  });

  group('after a provider sign-in', () {
    ProviderSession result({required bool created}) => ProviderSession(
          session: const Session(token: 'token-g', userId: 'user-2', email: 'gina@example.com'),
          created: created,
        );

    testWidgets('a new provider account lands on the referral prompt', (tester) async {
      client.onSignInWithGoogle = (_) async => result(created: true);
      final container = await pumpApp(
        tester,
        client: client,
        storage: FakeSessionStorage(),
        google: FakeProviderSignIn.google(),
      );

      await tester.tap(find.text('Continue with Google'));
      await tester.pumpAndSettle();

      expect(find.text('Have a referral code?'), findsOneWidget);
      expect(find.text('Trending'), findsNothing);
      expect(container.read(sessionProvider.notifier).justCreatedViaProvider, isFalse);
    });

    testWidgets('an existing provider account lands on home', (tester) async {
      client.onSignInWithGoogle = (_) async => result(created: false);
      await pumpApp(
        tester,
        client: client,
        storage: FakeSessionStorage(),
        google: FakeProviderSignIn.google(),
      );

      await tester.tap(find.text('Continue with Google'));
      await tester.pumpAndSettle();

      expect(find.text('Trending'), findsOneWidget);
      expect(find.text('Have a referral code?'), findsNothing);
    });

    testWidgets('email and password registration still lands on Confirm registration', (tester) async {
      await pumpApp(
        tester,
        client: client,
        storage: FakeSessionStorage(),
        google: FakeProviderSignIn.google(),
      );
      await tester.tap(find.text('Create an account'));
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
      await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
      await tester.pump();

      await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
      await tester.pumpAndSettle();

      expect(find.text('Confirm registration'), findsOneWidget);
      expect(find.text('Have a referral code?'), findsNothing);
    });

    testWidgets('signing out clears the pending prompt', (tester) async {
      client.onSignInWithGoogle = (_) async => result(created: true);
      final container = await pumpApp(
        tester,
        client: client,
        storage: FakeSessionStorage(),
        google: FakeProviderSignIn.google(),
        settle: true,
      );
      final notifier = container.read(sessionProvider.notifier);
      await notifier.signInWithProvider(
        const ProviderCredential(provider: SignInProvider.google, token: 't'),
      );
      expect(notifier.justCreatedViaProvider, isTrue);

      await notifier.signOut();

      expect(notifier.justCreatedViaProvider, isFalse);
    });
  });

  testWidgets('My creations opens from home and goes back', (tester) async {
    await pumpApp(tester, client: client, storage: FakeSessionStorage(savedSession));

    await tester.tap(find.byTooltip('My creations'));
    await tester.pumpAndSettle();

    expect(find.text('Your creations will appear here'), findsOneWidget);
    expect(find.text('Trending'), findsNothing);

    await tester.pageBack();
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('a creation opens its detail screen and goes back to the grid',
      (tester) async {
    final store = InMemoryCreationStore();
    await store.save(
      userId: 'user-1',
      jobId: 'job-1',
      label: 'astronaut on a beach',
      bytes: tinyPng,
      finishedAt: DateTime.utc(2026, 10, 19),
    );
    await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
      store: store,
    );

    await tester.tap(find.byTooltip('My creations'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('job-1')));
    await tester.pumpAndSettle();

    expect(find.text('astronaut on a beach'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('My creations'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('a signed-out user is redirected from My creations to sign-in',
      (tester) async {
    final container =
        await pumpApp(tester, client: client, storage: FakeSessionStorage());

    container.read(routerProvider).go('/creations');
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);

    container.read(routerProvider).go('/creations/job-1');
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(find.text('My creations'), findsNothing);
  });
}
