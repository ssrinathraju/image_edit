import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/features/history/creation_store.dart';
import 'package:image_edit/features/common/submit_controller.dart';
import 'package:image_edit/features/generation_status/generation_status_screen.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_edit/services/image_actions.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_image_actions.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';

GenerationJob _succeeded(String id) => GenerationJob(
      jobId: id,
      status: JobStatus.succeeded,
      resultUrl: 'http://fake/images/$id.png',
    );

GenerationRequest _request() => GenerationRequest(
      photo: XFile.fromData(tinyPng, name: 'me.png'),
      templateId: 'beach',
    );

class _Harness {
  _Harness({required this.client, required this.actions});

  final FakeApiClient client;
  final FakeImageActions actions;
}

Future<_Harness> _pump(
  WidgetTester tester, {
  FakeApiClient? client,
  GenerationRequest? lastRequest,
  bool showActions = true,
  String jobId = 'job-1',
  InMemoryCreationStore? store,
}) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);

  final fakeClient = client ?? FakeApiClient();
  if (client == null) fakeClient.onStatus = (id) async => _succeeded(id);
  fakeClient.onFetchBytes = (_) async => tinyPng;
  final actions = FakeImageActions();
  final router = GoRouter(
    initialLocation: '/status/$jobId',
    routes: [
      GoRoute(path: '/', builder: (_, _) => const Text('home')),
      GoRoute(
        path: '/status/:jobId',
        builder: (_, state) =>
            GenerationStatusScreen(jobId: state.pathParameters['jobId']!),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(fakeClient),
        creationStoreProvider.overrideWithValue(store ?? InMemoryCreationStore()),
        sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
        imageActionsProvider.overrideWithValue(actions),
        showImageActionsProvider.overrideWithValue(showActions),
        lastRequestProvider.overrideWith(
          (_) => lastRequest == null ? null : (jobId: 'job-1', request: lastRequest),
        ),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
  return _Harness(client: fakeClient, actions: actions);
}

void main() {
  testWidgets('a succeeded job shows the image and every action', (tester) async {
    await _pump(tester, lastRequest: _request());

    expect(find.byType(Image, skipOffstage: false), findsOneWidget);
    expect(find.text('Download'), findsOneWidget);
    expect(find.text('Share'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('Download and Share are hidden on web, other actions stay', (tester) async {
    await _pump(tester, lastRequest: _request(), showActions: false);

    expect(find.text('Download'), findsNothing);
    expect(find.text('Share'), findsNothing);
    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('Retry is hidden when there is no remembered request', (tester) async {
    await _pump(tester);

    expect(find.text('Retry'), findsNothing);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('a failed job shows the error, Retry, and New Generation', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (id) async =>
          GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed');
    await _pump(tester, client: client, lastRequest: _request());

    expect(find.text('pipeline_failed'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('New Generation'), findsOneWidget);
    expect(find.text('Download'), findsNothing);
  });

  testWidgets('Retry resubmits the same request and tracks the new job', (tester) async {
    final client = FakeApiClient();
    client.onStatus = (id) async => _succeeded(id);
    client.onSubmit = (_) async => 'job-2';
    final request = _request();
    await _pump(tester, client: client, lastRequest: request);

    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(client.submitted.single, same(request));
    expect(client.statusCalls, containsAllInOrder(['job-1', 'job-2']));
  });

  testWidgets('a failed poll shows a friendly message, not the raw exception', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (_) async => throw DioException(
            requestOptions: RequestOptions(path: '/generations/job-1'),
            message: 'connection error',
          );
    await _pump(tester, client: client);

    expect(find.textContaining('Could not reach the server'), findsOneWidget);
    expect(find.textContaining('DioException'), findsNothing);
  });

  testWidgets('Retry is hidden on a job the last request did not create', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (id) async =>
          GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed');
    await _pump(tester, client: client, lastRequest: _request(), jobId: 'job-9');

    expect(find.text('pipeline_failed'), findsOneWidget);
    expect(find.text('Retry'), findsNothing);
  });

  testWidgets('Home returns to the home screen', (tester) async {
    await _pump(tester);

    await tester.tap(find.text('Home'));
    await tester.pumpAndSettle();

    expect(find.text('home'), findsOneWidget);
  });

  testWidgets('Download saves the fetched bytes and confirms', (tester) async {
    final harness = await _pump(tester);

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();

    expect(harness.actions.saved.single.bytes, tinyPng);
    expect(harness.actions.saved.single.name, 'job-1');
    expect(find.text('Saved to your photo library.'), findsOneWidget);
  });

  testWidgets('Download explains a denied permission', (tester) async {
    final harness = await _pump(tester);
    harness.actions.saveResult = SaveResult.permissionDenied;

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Photo library access is required'), findsOneWidget);
  });

  testWidgets('Share hands the fetched bytes to the share sheet', (tester) async {
    final harness = await _pump(tester);

    await tester.tap(find.text('Share'));
    await tester.pumpAndSettle();

    expect(harness.actions.shared.single.bytes, tinyPng);
    expect(harness.actions.shared.single.name, 'job-1');
  });

  testWidgets('a succeeded job is saved once, with the label from the pending entry',
      (tester) async {
    final store = InMemoryCreationStore();
    await store.remember(
      userId: 'user-1',
      jobId: 'job-1',
      label: 'astronaut on a beach',
      submittedAt: DateTime.utc(2026, 10, 19),
    );

    await _pump(tester, store: store);
    await tester.pump(const Duration(seconds: 3));

    final creations = await store.list('user-1');
    expect(creations.single.jobId, 'job-1');
    expect(creations.single.label, 'astronaut on a beach');
    expect(store.savedJobs, ['job-1']);
    expect(await store.pending('user-1'), isEmpty);
  });

  testWidgets('a job with no pending entry is saved with an empty label', (tester) async {
    final store = InMemoryCreationStore();

    await _pump(tester, store: store);

    expect((await store.list('user-1')).single.label, '');
  });

  testWidgets('rebuilding the screen does not save again', (tester) async {
    final store = InMemoryCreationStore();
    final harness = await _pump(tester, store: store);

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 5));

    expect(harness.actions.saved, hasLength(1));
    expect(store.savedJobs, ['job-1']);
  });

  testWidgets('opening a saved job again keeps one creation', (tester) async {
    final store = InMemoryCreationStore();
    await _pump(tester, store: store);
    await tester.pumpWidget(const SizedBox());
    await _pump(tester, store: store);

    expect(await store.list('user-1'), hasLength(1));
  });

  testWidgets('a store that fails keeps the image and actions and says so', (tester) async {
    final store = InMemoryCreationStore()..saveError = StateError('disk full');

    await _pump(tester, store: store);

    expect(find.text("Couldn't save to My creations"), findsOneWidget);
    expect(find.byType(Image, skipOffstage: false), findsOneWidget);
    expect(find.text('Download'), findsOneWidget);
    expect(find.text('Share'), findsOneWidget);
  });

  testWidgets('a failed job saves nothing', (tester) async {
    final store = InMemoryCreationStore();
    final client = FakeApiClient()
      ..onStatus = (id) async =>
          GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed');

    await _pump(tester, client: client, store: store);

    expect(store.savedJobs, isEmpty);
    expect(find.text("Couldn't save to My creations"), findsNothing);
  });
}
