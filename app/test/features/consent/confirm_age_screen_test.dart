import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;
late bool confirmed;

Future<void> _openUnconfirmed(WidgetTester tester, {DateTime? birthDate}) async {
  await pumpApp(tester, client: client, storage: storage, birthDate: birthDate);
}

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage(savedSession);
    confirmed = false;
    client.onFetchMe = () async => fakeProfile(ageConfirmed: confirmed);
    client.onConfirmAge = (_) async => confirmed = true;
  });

  testWidgets('an unconfirmed account sees Confirm your age instead of home', (tester) async {
    await _openUnconfirmed(tester);

    expect(find.text('Confirm your age'), findsOneWidget);
    expect(find.text('Trending'), findsNothing);
    expect(
      tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirm')).onPressed,
      isNull,
    );
  });

  testWidgets('an adult date opens home and the screen does not come back', (tester) async {
    await _openUnconfirmed(tester, birthDate: DateTime(1990, 1, 31));

    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    expect(client.confirmedAges, [DateTime(1990, 1, 31)]);
    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Confirm your age'), findsNothing);
  });

  testWidgets('an under-18 date shows the blocked screen with Delete account and Sign out only', (tester) async {
    client.onConfirmAge = (_) async =>
        throw apiError(403, 'under_age', 'you must be 18 or older to use this app');
    await _openUnconfirmed(tester);

    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    expect(
      find.text("This account can't be used because you must be 18 or older."),
      findsOneWidget,
    );
    expect(find.widgetWithText(FilledButton, 'Delete account'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Sign out'), findsOneWidget);
    expect(find.text('Trending'), findsNothing);
    expect(find.text('Confirm your age'), findsNothing);
  });

  testWidgets('Sign out on the blocked screen ends the session', (tester) async {
    client.onConfirmAge = (_) async => throw apiError(403, 'under_age', 'x');
    await _openUnconfirmed(tester);
    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, 'Sign out'));
    await tester.pumpAndSettle();

    expect(client.logoutCalls, 1);
    expect(storage.saved, isNull);
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
  });

  testWidgets('Delete account on the blocked screen deletes with the password', (tester) async {
    client.onConfirmAge = (_) async => throw apiError(403, 'under_age', 'x');
    await _openUnconfirmed(tester);
    await chooseDateOfBirth(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.descendant(of: find.byType(AlertDialog), matching: find.byType(TextField)),
      'password-1',
    );
    await tester.pump();
    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.widgetWithText(FilledButton, 'Delete account'),
      ),
    );
    await tester.pumpAndSettle();

    expect(client.deletedWith, ['password-1']);
    expect(storage.saved, isNull);
    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
  });

  testWidgets('a network failure keeps the screen and offers another try', (tester) async {
    var first = true;
    client.onConfirmAge = (_) async {
      if (first) {
        first = false;
        throw StateError('offline');
      }
      confirmed = true;
    };
    await _openUnconfirmed(tester);
    await chooseDateOfBirth(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();
    expect(find.text("Couldn't confirm, try again"), findsOneWidget);
    expect(find.text('Confirm your age'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('an account the server already holds as confirmed goes home', (tester) async {
    client.onConfirmAge = (_) async {
      confirmed = true;
      throw apiError(409, 'age_already_confirmed', 'x');
    };
    await _openUnconfirmed(tester);
    await chooseDateOfBirth(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
  });
}
