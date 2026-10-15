import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/schemas/job.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';
import '../../support/screen_harness.dart' show pickPhoto;

void main() {
  testWidgets('shows the remaining count including bonus credits', (tester) async {
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(usedToday: 2, bonusCredits: 5);

    await pumpApp(tester, client: client, storage: FakeSessionStorage(savedSession));

    expect(find.text('6 generations left today'), findsOneWidget);
  });

  testWidgets('hides the chip when the server sends no usage', (tester) async {
    await pumpApp(
      tester,
      client: FakeApiClient(),
      storage: FakeSessionStorage(savedSession),
    );

    expect(find.textContaining('left today'), findsNothing);
  });

  testWidgets('the count drops after a submission', (tester) async {
    var used = 0;
    final client = FakeApiClient();
    client.onFetchMe = () async => fakeProfile(usedToday: used);
    client.onSubmit = (_) async {
      used = 1;
      return 'job-1';
    };
    client.onStatus =
        (id) async => GenerationJob(jobId: id, status: JobStatus.queued);
    final container = await pumpApp(
      tester,
      client: client,
      storage: FakeSessionStorage(savedSession),
    );
    expect(find.text('3 generations left today'), findsOneWidget);

    await tester.tap(find.text('Create your own'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'a cat in space');
    await pickPhoto(tester);
    await tester.tap(find.text('Generate'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    container.read(routerProvider).go('/');
    await tester.pumpAndSettle();

    expect(find.text('2 generations left today'), findsOneWidget);
  });
}
