import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/profile/profile_providers.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;

Future<FakeLinkLauncher> _openProfile(
  WidgetTester tester, {
  ProfileLinks links = const ProfileLinks(),
}) async {
  final launcher = FakeLinkLauncher();
  await pumpApp(
    tester,
    client: client,
    storage: storage,
    links: links,
    launcher: launcher,
  );
  await tester.tap(find.byTooltip('Profile'));
  await tester.pumpAndSettle();
  return launcher;
}

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage(savedSession);
  });

  testWidgets('the home icon opens the profile and back returns home', (tester) async {
    await _openProfile(tester);

    expect(find.text('Profile'), findsOneWidget);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('the header shows the email, its initial, and the version', (tester) async {
    await _openProfile(tester);

    expect(find.text('ana@example.com'), findsOneWidget);
    expect(find.text('A'), findsOneWidget);
    expect(find.text('Version 1.2.3 (45)'), findsOneWidget);
  });

  testWidgets('unconfigured links are hidden', (tester) async {
    await _openProfile(tester);

    expect(find.text('Help and feedback'), findsNothing);
    expect(find.text('Privacy policy'), findsNothing);
    expect(find.text('Terms'), findsNothing);
  });

  testWidgets('configured links are shown and open their address', (tester) async {
    final launcher = await _openProfile(
      tester,
      links: const ProfileLinks(
        privacyUrl: 'https://example.com/privacy',
        supportEmail: 'help@example.com',
      ),
    );

    expect(find.text('Privacy policy'), findsOneWidget);
    expect(find.text('Help and feedback'), findsOneWidget);
    expect(find.text('Terms'), findsNothing);

    await tester.tap(find.text('Privacy policy'));
    await tester.pumpAndSettle();
    expect(launcher.opened.single.toString(), 'https://example.com/privacy');

    await tester.tap(find.text('Help and feedback'));
    await tester.pumpAndSettle();
    expect(launcher.opened.last.toString(), 'mailto:help@example.com');
  });

  testWidgets('a link that cannot open shows a snackbar', (tester) async {
    final launcher = await _openProfile(
      tester,
      links: const ProfileLinks(termsUrl: 'https://example.com/terms'),
    );
    launcher.result = false;

    await tester.tap(find.text('Terms'));
    await tester.pumpAndSettle();

    expect(find.text('Could not open the link.'), findsOneWidget);
  });

  group('log out', () {
    testWidgets('confirming returns to sign-in and clears the session', (tester) async {
      await _openProfile(tester);

      await tester.tap(find.widgetWithText(ListTile, 'Log out'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Log out'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
      expect(client.logoutCalls, 1);
      expect(storage.saved, isNull);
    });

    testWidgets('cancelling does nothing', (tester) async {
      await _openProfile(tester);

      await tester.tap(find.widgetWithText(ListTile, 'Log out'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Profile'), findsOneWidget);
      expect(client.logoutCalls, 0);
      expect(storage.saved, savedSession);
    });
  });

  group('delete account', () {
    Future<void> openDialog(WidgetTester tester) async {
      await tester.tap(find.widgetWithText(ListTile, 'Delete account'));
      await tester.pumpAndSettle();
    }

    FilledButton deleteButton(WidgetTester tester) => tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, 'Delete account'),
        );

    testWidgets('the destructive button is disabled until a password is typed', (tester) async {
      await _openProfile(tester);
      await openDialog(tester);

      expect(find.textContaining('permanent'), findsOneWidget);
      expect(deleteButton(tester).onPressed, isNull);

      await tester.enterText(find.byType(TextField), 'password-1');
      await tester.pump();
      expect(deleteButton(tester).onPressed, isNotNull);
    });

    testWidgets('success returns to sign-in', (tester) async {
      await _openProfile(tester);
      await openDialog(tester);

      await tester.enterText(find.byType(TextField), 'password-1');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
      await tester.pumpAndSettle();

      expect(client.deletedWith, ['password-1']);
      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
      expect(storage.saved, isNull);
    });

    testWidgets('a wrong password keeps the user on the profile with a message', (tester) async {
      client.onDeleteAccount = (_) async =>
          throw apiError(403, 'invalid_password', 'password is incorrect');
      await _openProfile(tester);
      await openDialog(tester);

      await tester.enterText(find.byType(TextField), 'nope');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
      await tester.pumpAndSettle();

      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('password is incorrect'), findsOneWidget);
      expect(storage.saved, savedSession);
    });

    testWidgets('cancelling does not call the server', (tester) async {
      await _openProfile(tester);
      await openDialog(tester);

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(client.deletedWith, isEmpty);
    });
  });
}
