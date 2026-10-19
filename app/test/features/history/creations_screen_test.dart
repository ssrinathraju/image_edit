import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/history/creation_store.dart';
import 'package:image_edit/features/history/creations_screen.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/services/generation_providers.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';

Future<void> _save(
  InMemoryCreationStore store,
  String jobId,
  DateTime finishedAt, {
  String userId = 'user-1',
}) =>
    store.save(
      userId: userId,
      jobId: jobId,
      label: 'label $jobId',
      bytes: tinyPng,
      finishedAt: finishedAt,
    );

Future<void> _pump(
  WidgetTester tester,
  InMemoryCreationStore store, {
  FakeApiClient? client,
  FakeSessionStorage? storage,
}) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => const CreationsScreen()),
      GoRoute(
        path: '/creations/:jobId',
        builder: (_, state) => Text('detail:${state.pathParameters['jobId']}'),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(client ?? FakeApiClient()),
        sessionStorageProvider
            .overrideWithValue(storage ?? FakeSessionStorage(savedSession)),
        creationStoreProvider.overrideWithValue(store),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

double _top(WidgetTester tester, String jobId) =>
    tester.getTopLeft(find.byKey(ValueKey(jobId))).dy * 1000 +
    tester.getTopLeft(find.byKey(ValueKey(jobId))).dx;

void main() {
  testWidgets('the newest creation comes first', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store, 'monday', DateTime.utc(2026, 10, 19));
    await _save(store, 'tuesday', DateTime.utc(2026, 10, 20));

    await _pump(tester, store);

    expect(find.byType(Image), findsNWidgets(2));
    expect(_top(tester, 'tuesday'), lessThan(_top(tester, 'monday')));
  });

  testWidgets('with no creations it says they will appear here', (tester) async {
    await _pump(tester, InMemoryCreationStore());

    expect(find.text('Your creations will appear here'), findsOneWidget);
    expect(find.byType(GridView), findsNothing);
  });

  testWidgets("another account's creations are not shown", (tester) async {
    final store = InMemoryCreationStore();
    await _save(store, 'theirs', DateTime.utc(2026, 10, 19), userId: 'user-2');

    await _pump(tester, store);

    expect(find.text('Your creations will appear here'), findsOneWidget);
  });

  testWidgets('a creation whose file is missing shows a placeholder', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store, 'job-1', DateTime.utc(2026, 10, 19));
    File('${store.imageDirectory.path}/job-1.png').deleteSync();

    await _pump(tester, store);
    // Reading the missing file is real I/O, which the fake clock cannot run,
    // and the error needs a few frames to reach the widget.
    for (var i = 0; i < 5; i++) {
      await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50)));
      await tester.pump(const Duration(milliseconds: 50));
    }

    expect(find.byIcon(Icons.broken_image_outlined), findsOneWidget);
  });

  testWidgets('a cell opens the detail screen', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store, 'job-1', DateTime.utc(2026, 10, 19));
    await _pump(tester, store);

    await tester.tap(find.byKey(const ValueKey('job-1')));
    await tester.pumpAndSettle();

    expect(find.text('detail:job-1'), findsOneWidget);
  });

  testWidgets('a creation saved by the catch-up appears without leaving', (tester) async {
    final store = InMemoryCreationStore();
    await store.remember(
      userId: 'user-1',
      jobId: 'late',
      label: 'finished meanwhile',
      submittedAt: DateTime.now(),
    );
    final gate = Completer<GenerationJob>();
    final client = FakeApiClient();
    client.onStatus = (_) => gate.future;
    client.onFetchBytes = (_) async => tinyPng;

    await _pump(tester, store, client: client);
    expect(find.text('Your creations will appear here'), findsOneWidget);

    gate.complete(
      const GenerationJob(
        jobId: 'late',
        status: JobStatus.succeeded,
        resultUrl: 'http://fake/late.png',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Your creations will appear here'), findsNothing);
    expect(find.byKey(const ValueKey('late')), findsOneWidget);
  });

  testWidgets('opening the screen starts a catch-up', (tester) async {
    final store = InMemoryCreationStore();
    await store.remember(
      userId: 'user-1',
      jobId: 'late',
      label: '',
      submittedAt: DateTime.now(),
    );
    final client = FakeApiClient();

    await _pump(tester, store, client: client);

    expect(client.statusCalls, ['late']);
  });
}
