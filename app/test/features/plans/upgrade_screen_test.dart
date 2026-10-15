import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/router.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

void main() {
  testWidgets('shows both daily limits and says payments are not available', (tester) async {
    final client = FakeApiClient()..onFetchMe = () async => fakeProfile();
    final container = await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
    );

    container.read(routerProvider).go('/upgrade');
    await tester.pumpAndSettle();

    expect(find.text('3 generations per day'), findsOneWidget);
    expect(find.text('30 generations per day'), findsOneWidget);
    expect(find.text('Payments are not available yet'), findsOneWidget);
  });

  testWidgets('has no control that could submit a purchase', (tester) async {
    final client = FakeApiClient()..onFetchMe = () async => fakeProfile();
    final container = await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
    );

    container.read(routerProvider).go('/upgrade');
    await tester.pumpAndSettle();

    expect(find.byType(FilledButton), findsNothing);
    expect(find.byType(ElevatedButton), findsNothing);
    expect(find.byType(OutlinedButton), findsNothing);
    expect(find.byType(TextField), findsNothing);
  });
}
