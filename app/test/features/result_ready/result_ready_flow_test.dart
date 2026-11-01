import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/schemas/job.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';
import '../../support/screen_harness.dart';

const _bannerText = 'Your image is ready';

late FakeApiClient client;
late InMemoryCreationStore store;
late ProviderContainer container;
late JobStatus jobStatus;

Future<void> _submitFromCreate(WidgetTester tester) async {
  client = FakeApiClient();
  client.onFetchBytes = (_) async => tinyPng;
  client.onStatus = (id) async => GenerationJob(
        jobId: id,
        status: jobStatus,
        resultUrl: jobStatus == JobStatus.succeeded ? 'http://fake/$id.png' : null,
        expiresAt: DateTime.utc(2026, 12, 1),
        error: jobStatus == JobStatus.failed ? 'generation_failed' : null,
      );
  store = InMemoryCreationStore();
  container = await pumpApp(
    tester,
    client: client,
    storage: FakeSessionStorage(savedSession),
    store: store,
    useImageEditApp: true,
  );
  container.read(routerProvider).go('/create');
  await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField), 'a cat in space');
  await tester.pump();
  await pickPhoto(tester);
  await tester.tap(find.text('Generate'));
  // The status screen's spinner never settles.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
  expect(client.submitted, hasLength(1));
}

Future<void> _waitForWatcher(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 5));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  setUp(() => jobStatus = JobStatus.running);

  testWidgets('a result that finishes while on the profile is saved and announced', (tester) async {
    await _submitFromCreate(tester);
    container.read(routerProvider).go('/profile');
    await tester.pumpAndSettle();
    expect(store.savedJobs, isEmpty);

    jobStatus = JobStatus.succeeded;
    await _waitForWatcher(tester);

    expect(store.creations['user-1'], hasLength(1));
    expect(find.text(_bannerText), findsOneWidget);
    expect(find.text('View'), findsOneWidget);
  });

  testWidgets('a job that fails shows no banner', (tester) async {
    await _submitFromCreate(tester);
    container.read(routerProvider).go('/profile');
    await tester.pumpAndSettle();

    jobStatus = JobStatus.failed;
    await _waitForWatcher(tester);

    expect(store.savedJobs, isEmpty);
    expect(find.text(_bannerText), findsNothing);
  });

  testWidgets('staying on the status screen shows no banner and saves once', (tester) async {
    await _submitFromCreate(tester);

    jobStatus = JobStatus.succeeded;
    await _waitForWatcher(tester);
    await tester.pump(const Duration(seconds: 2));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text(_bannerText), findsNothing);
    expect(store.creations['user-1'], hasLength(1));
    expect(store.creations['user-1']!.single.jobId, 'job-1');
    expect(find.textContaining('Saved to My creations'), findsOneWidget);
  });
}
