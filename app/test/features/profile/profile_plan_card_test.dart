import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/account.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

Future<void> _openProfile(WidgetTester tester, FakeApiClient client) async {
  await pumpApp(tester, client: client, storage: FakeSessionStorage(savedSession));
  await tester.tap(find.byTooltip('Profile'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('free plan card shows usage, bonus credits, and Upgrade', (tester) async {
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(usedToday: 2, bonusCredits: 5);

    await _openProfile(tester, client);

    expect(find.text('Free plan'), findsOneWidget);
    expect(find.text('2 of 3 used today'), findsOneWidget);
    expect(find.text('5 bonus credits'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Upgrade'), findsOneWidget);
  });

  testWidgets('premium plan card has no Upgrade action', (tester) async {
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(
            plan: Plan.premium,
            dailyLimit: 30,
            usedToday: 4,
          );

    await _openProfile(tester, client);

    expect(find.text('Premium plan'), findsOneWidget);
    expect(find.text('4 of 30 used today'), findsOneWidget);
    expect(find.text('Upgrade'), findsNothing);
  });

  testWidgets('opening the profile reloads the usage', (tester) async {
    var used = 0;
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(usedToday: used);
    await pumpApp(tester, client: client, storage: FakeSessionStorage(savedSession));
    used = 3;

    await tester.tap(find.byTooltip('Profile'));
    await tester.pumpAndSettle();

    expect(find.text('3 of 3 used today'), findsOneWidget);
  });

  testWidgets('no plan card when the server sends no usage', (tester) async {
    await _openProfile(tester, FakeApiClient());

    expect(find.textContaining('plan'), findsNothing);
    expect(find.text('Invite friends'), findsOneWidget);
  });
}
