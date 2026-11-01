import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/history/history_sync.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/schemas/job.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';

const _bannerText = 'Your image is ready';

late FakeApiClient client;
late InMemoryCreationStore store;
late ProviderContainer container;

Future<void> _pump(WidgetTester tester) async {
  client = FakeApiClient();
  client.onFetchBytes = (_) async => tinyPng;
  client.onStatus = (id) async => GenerationJob(
        jobId: id,
        status: JobStatus.succeeded,
        resultUrl: 'http://fake/$id.png',
      );
  store = InMemoryCreationStore();
  container = await pumpApp(
    tester,
    client: client,
    storage: FakeSessionStorage(savedSession),
    store: store,
    useImageEditApp: true,
  );
}

Future<void> _remember(String jobId, {String userId = 'user-1'}) =>
    store.remember(
      userId: userId,
      jobId: jobId,
      label: 'label',
      submittedAt: DateTime.now(),
    );

/// Lets the watcher's next 5-second tick run and the banner appear.
Future<void> _waitForWatcher(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 5));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

String _location() => container
    .read(routerProvider)
    .routerDelegate
    .currentConfiguration
    .last
    .matchedLocation;

void main() {
  testWidgets('a saved result shows the banner on home', (tester) async {
    await _pump(tester);
    await _remember('job-1');

    await _waitForWatcher(tester);

    expect(find.text(_bannerText), findsOneWidget);
    expect(find.text('View'), findsOneWidget);
    expect(store.savedJobs, ['job-1']);
  });

  testWidgets('View opens the creation and Back returns home', (tester) async {
    await _pump(tester);
    await _remember('job-1');
    await _waitForWatcher(tester);

    await tester.tap(find.text('View'));
    await tester.pumpAndSettle();

    expect(_location(), '/creations/job-1');
    expect(find.byType(Image, skipOffstage: false), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(_location(), '/');
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('the banner goes away after 4 seconds and the creation stays', (tester) async {
    await _pump(tester);
    await _remember('job-1');
    await _waitForWatcher(tester);

    await tester.pump(const Duration(seconds: 4));
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text(_bannerText), findsNothing);
    expect(store.creations['user-1'], hasLength(1));
  });

  testWidgets('no banner on the status screen of the same job', (tester) async {
    await _pump(tester);
    await _remember('job-1');
    container.read(routerProvider).go('/status/job-1');
    await tester.pump();

    await _waitForWatcher(tester);

    expect(find.text(_bannerText), findsNothing);
    expect(store.savedJobs, contains('job-1'));
  });

  testWidgets('a banner on the status screen of another job', (tester) async {
    await _pump(tester);
    await _remember('job-2');
    container.read(routerProvider).go('/status/job-1');
    await tester.pump();

    await _waitForWatcher(tester);

    expect(find.text(_bannerText), findsOneWidget);
  });

  testWidgets('two results show two banners one after the other', (tester) async {
    await _pump(tester);
    await _remember('job-1');
    await _remember('job-2');
    await _waitForWatcher(tester);

    expect(find.text(_bannerText), findsOneWidget);
    await tester.tap(find.text('View'));
    await tester.pumpAndSettle();
    expect(_location(), '/creations/job-1');

    expect(find.text(_bannerText), findsOneWidget);
    await tester.tap(find.text('View'));
    await tester.pumpAndSettle();
    expect(_location(), '/creations/job-2');
  });

  testWidgets('an event for another account shows nothing', (tester) async {
    await _pump(tester);
    await _remember('job-9', userId: 'user-2');

    await container.read(historySyncProvider).run('user-2');
    await tester.pump(const Duration(milliseconds: 300));

    expect(store.creations['user-2'], hasLength(1));
    expect(find.text(_bannerText), findsNothing);
  });

  testWidgets('no banner after the account signed out', (tester) async {
    await _pump(tester);
    await _remember('job-1');
    final sync = container.read(historySyncProvider);
    await container.read(sessionProvider.notifier).signOut();
    await tester.pumpAndSettle();

    await sync.run('user-1');
    await tester.pump(const Duration(milliseconds: 300));

    expect(store.savedJobs, ['job-1']);
    expect(find.text(_bannerText), findsNothing);
  });
}
