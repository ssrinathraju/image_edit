import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/history/creation_detail_screen.dart';
import 'package:image_edit/features/history/creation_store.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_edit/services/image_actions.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_image_actions.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';

final _finishedAt = DateTime(2026, 10, 19, 10, 30);

Future<void> _save(
  InMemoryCreationStore store, {
  String label = 'astronaut on a beach',
}) =>
    store.save(
      userId: 'user-1',
      jobId: 'job-1',
      label: label,
      bytes: tinyPng,
      finishedAt: _finishedAt,
    );

Future<FakeImageActions> _pump(
  WidgetTester tester,
  InMemoryCreationStore store, {
  FakeApiClient? client,
}) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final actions = FakeImageActions();
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => const Text('grid')),
      GoRoute(
        path: '/creations/:jobId',
        builder: (_, state) =>
            CreationDetailScreen(jobId: state.pathParameters['jobId']!),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(client ?? FakeApiClient()),
        sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
        creationStoreProvider.overrideWithValue(store),
        imageActionsProvider.overrideWithValue(actions),
        showImageActionsProvider.overrideWithValue(true),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
  unawaited(router.push<void>('/creations/job-1'));
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
  await tester.pumpAndSettle();
  return actions;
}

void main() {
  testWidgets('shows the image, label and date', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);

    await _pump(tester, store);

    expect(find.byType(Image, skipOffstage: false), findsOneWidget);
    expect(find.text('astronaut on a beach'), findsOneWidget);
    expect(find.textContaining('Oct 19'), findsOneWidget);
    expect(find.textContaining('10:30'), findsOneWidget);
  });

  testWidgets('an empty label reads as Creation', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store, label: '');

    await _pump(tester, store);

    // The app bar title is also "Creation"; the label is the second one.
    expect(find.text('Creation'), findsNWidgets(2));
  });

  testWidgets('never contacts the server', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    final client = FakeApiClient();
    client.onFetchBytes = (_) async => throw StateError('offline');
    client.onStatus = (_) async => throw StateError('offline');

    await _pump(tester, store, client: client);

    expect(find.byType(Image, skipOffstage: false), findsOneWidget);
    expect(client.statusCalls, isEmpty);
  });

  testWidgets('Download saves the stored bytes and confirms', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    final actions = await _pump(tester, store);

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();

    expect(actions.saved.single.bytes, tinyPng);
    expect(actions.saved.single.name, 'job-1');
    expect(find.text('Saved to your photo library.'), findsOneWidget);
  });

  testWidgets('Download explains a denied permission', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    final actions = await _pump(tester, store);
    actions.saveResult = SaveResult.permissionDenied;

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Photo library access is required'), findsOneWidget);
  });

  testWidgets('Share hands the stored bytes to the share sheet', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    final actions = await _pump(tester, store);

    await tester.tap(find.text('Share'));
    await tester.pumpAndSettle();

    expect(actions.shared.single.bytes, tinyPng);
  });

  testWidgets('a confirmed delete removes the creation and returns to the grid',
      (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    await _pump(tester, store);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(await store.list('user-1'), isEmpty);
    expect(find.text('grid'), findsOneWidget);
    expect(find.byType(CreationDetailScreen), findsNothing);
  });

  testWidgets('a cancelled delete changes nothing', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    await _pump(tester, store);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(await store.list('user-1'), hasLength(1));
    expect(find.byType(CreationDetailScreen), findsOneWidget);
    expect(find.text('astronaut on a beach'), findsOneWidget);
  });

  testWidgets('a missing image says so and still offers Delete', (tester) async {
    final store = InMemoryCreationStore();
    await _save(store);
    store.images.clear();

    await _pump(tester, store);

    expect(find.text('This image is no longer available'), findsOneWidget);
    expect(find.byType(Image, skipOffstage: false), findsNothing);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(await store.list('user-1'), isEmpty);
    expect(find.text('grid'), findsOneWidget);
  });

  testWidgets('a delete that fails keeps the screen and says so', (tester) async {
    final store = _FailingDeleteStore();
    await _save(store);
    await _pump(tester, store);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(find.text('Could not delete the creation.'), findsOneWidget);
    expect(find.text('astronaut on a beach'), findsOneWidget);
  });
}

class _FailingDeleteStore extends InMemoryCreationStore {
  @override
  Future<void> delete(String userId, String jobId) async =>
      throw StateError('disk error');
}
