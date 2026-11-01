import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/features/history/creation_store.dart';
import 'package:image_edit/features/common/photo_picker_field.dart';
import 'package:image_edit/features/common/submit_controller.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';
import 'package:image_edit/features/generation_status/generation_status_screen.dart';
import 'package:image_edit/schemas/creation.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_edit/services/image_actions.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_image_actions.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';

GenerationJob _succeeded(String id, {DateTime? expiresAt}) => GenerationJob(
      jobId: id,
      status: JobStatus.succeeded,
      resultUrl: 'http://fake/images/$id.png',
      expiresAt: expiresAt,
    );

final _expiry = DateTime.utc(2026, 10, 23, 10);

/// A store whose save finishes only when the test says so.
class _SlowStore extends InMemoryCreationStore {
  final release = Completer<void>();

  @override
  Future<void> save({
    required String userId,
    required String jobId,
    required String label,
    required Uint8List bytes,
    required DateTime finishedAt,
    CreationSource? source,
  }) async {
    await release.future;
    return super.save(
      userId: userId,
      jobId: jobId,
      label: label,
      bytes: bytes,
      finishedAt: finishedAt,
      source: source,
    );
  }
}

GenerationRequest _request() => GenerationRequest(
      photo: XFile.fromData(tinyPng, name: 'me.png'),
      templateId: 'beach',
    );

GenerationRequest _promptRequest([String prompt = 'astronaut on a beach']) =>
    GenerationRequest(
      photo: XFile.fromData(tinyPng, name: 'me.png'),
      prompt: prompt,
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
  DateTime Function(DateTime)? toLocal,
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
        path: '/create',
        builder: (_, state) => CustomGenerationScreen(
          initialPrompt: state.uri.queryParameters['prompt'] ?? '',
          initialPhoto: state.extra is XFile ? state.extra! as XFile : null,
        ),
      ),
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
        if (toLocal != null) expiryToLocalProvider.overrideWithValue(toLocal),
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

const _pipelineFailedText =
    "We couldn't create your image this time. This one wasn't counted, so try again.";
const _generalFailureText =
    "Something went wrong and this one wasn't counted. Please try again.";

void main() {
  testWidgets('a succeeded job shows the image and every action', (tester) async {
    await _pump(tester, lastRequest: _request());

    expect(find.byType(Image, skipOffstage: false), findsOneWidget);
    expect(find.text('Download'), findsOneWidget);
    expect(find.text('Share'), findsOneWidget);
    expect(find.text('More like this'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('Report from the status screen sends the job id, category and image', (tester) async {
    final harness = await _pump(tester, lastRequest: _request());

    await tester.tap(find.text('Report'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Violence or gore'));
    await tester.pump();
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    final report = harness.client.submittedReports.single;
    expect(report.jobId, 'job-1');
    expect(report.category, 'violence');
    expect(report.imageBytes, tinyPng);
    expect(find.text("Thanks, we'll review it."), findsOneWidget);
  });

  testWidgets('Report stays available on web where Download and Share are hidden', (tester) async {
    await _pump(tester, lastRequest: _request(), showActions: false);

    expect(find.text('Download'), findsNothing);
    expect(find.text('Report'), findsOneWidget);
  });

  testWidgets('Download and Share are hidden on web, other actions stay', (tester) async {
    await _pump(tester, lastRequest: _request(), showActions: false);

    expect(find.text('Download'), findsNothing);
    expect(find.text('Share'), findsNothing);
    expect(find.text('More like this'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('More like this is hidden when there is no remembered request', (tester) async {
    await _pump(tester);

    expect(find.text('More like this'), findsNothing);
    expect(find.text('Try again'), findsNothing);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('a failed job shows the error, Try again, and New Generation', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (id) async =>
          GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed');
    await _pump(tester, client: client, lastRequest: _request());

    expect(find.text(_pipelineFailedText), findsOneWidget);
    expect(find.text('pipeline_failed'), findsNothing);
    expect(find.text('Try again'), findsOneWidget);
    expect(find.text('More like this'), findsNothing);
    expect(find.text('New Generation'), findsOneWidget);
    expect(find.text('Download'), findsNothing);
  });

  testWidgets('a content_blocked job shows the content-rules message and no image', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (id) async =>
          GenerationJob(jobId: id, status: JobStatus.failed, error: 'content_blocked');
    await _pump(tester, client: client, lastRequest: _request());

    expect(
      find.text("This image was blocked by our content rules and wasn't counted."),
      findsOneWidget,
    );
    expect(find.text('content_blocked'), findsNothing);
    expect(find.byType(Image), findsNothing);
    expect(find.text('Report'), findsNothing);
    expect(find.text('New Generation'), findsOneWidget);
  });

  for (final code in <String?>['quota_exploded', null]) {
    testWidgets('a failed job with code $code shows the general message', (tester) async {
      final client = FakeApiClient()
        ..onStatus = (id) async =>
            GenerationJob(jobId: id, status: JobStatus.failed, error: code);
      await _pump(tester, client: client);

      expect(find.text(_generalFailureText), findsOneWidget);
      if (code != null) expect(find.text(code), findsNothing);
    });
  }

  testWidgets('More like this resubmits the same request and tracks the new job', (tester) async {
    final client = FakeApiClient();
    client.onStatus = (id) async => _succeeded(id);
    client.onSubmit = (_) async => 'job-2';
    final request = _request();
    await _pump(tester, client: client, lastRequest: request);

    await tester.tap(find.text('More like this'));
    await tester.pumpAndSettle();

    expect(client.submitted.single, same(request));
    expect(client.statusCalls, containsAllInOrder(['job-1', 'job-2']));
  });

  testWidgets('Try again after a failure submits the same request', (tester) async {
    final client = FakeApiClient();
    client.onStatus = (id) async => id == 'job-1'
        ? GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed')
        : _succeeded(id);
    client.onSubmit = (_) async => 'job-2';
    final request = _request();
    await _pump(tester, client: client, lastRequest: request);

    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();

    expect(client.submitted.single, same(request));
    expect(client.statusCalls, contains('job-2'));
  });

  testWidgets('no action is offered once the last request was cleared', (tester) async {
    await _pump(tester, lastRequest: _request());
    final container = ProviderScope.containerOf(tester.element(find.byType(MaterialApp)));

    container.read(lastRequestProvider.notifier).state = null;
    await tester.pump();

    expect(find.text('More like this'), findsNothing);
    expect(find.text('Edit prompt'), findsNothing);
    expect(find.text('Home'), findsOneWidget);
  });

  testWidgets('a quota refusal shows the limit dialog and opens no new job', (tester) async {
    final client = FakeApiClient();
    client.onStatus = (id) async => _succeeded(id);
    client.onSubmit = (_) async => throw apiError(
          429,
          'quota_exceeded',
          'the daily generation limit has been reached',
        );
    await _pump(tester, client: client, lastRequest: _request());

    await tester.tap(find.text('More like this'));
    await tester.pumpAndSettle();

    expect(find.text('Daily limit reached'), findsOneWidget);
    expect(client.statusCalls.toSet(), {'job-1'});
  });

  testWidgets('a double tap on More like this submits once', (tester) async {
    final release = Completer<String>();
    final client = FakeApiClient();
    client.onStatus = (id) async => _succeeded(id);
    client.onSubmit = (_) => release.future;
    await _pump(tester, client: client, lastRequest: _request());

    await tester.tap(find.text('More like this'));
    await tester.pump();
    await tester.tap(find.text('More like this'), warnIfMissed: false);
    await tester.pump();
    release.complete('job-2');
    await tester.pumpAndSettle();

    expect(client.submitted, hasLength(1));
  });

  testWidgets('the watched save keeps the pending entry source', (tester) async {
    final store = InMemoryCreationStore();
    await store.remember(
      userId: 'user-1',
      jobId: 'job-1',
      label: 'Beach',
      submittedAt: DateTime.utc(2026, 10, 19),
      source: const CreationSource.template('beach'),
    );

    await _pump(tester, store: store);

    expect((await store.list('user-1')).single.source?.templateId, 'beach');
  });

  testWidgets('without a pending entry the save takes the source from the request',
      (tester) async {
    final store = InMemoryCreationStore();

    await _pump(tester, store: store, lastRequest: _promptRequest());

    expect((await store.list('user-1')).single.source?.prompt, 'astronaut on a beach');
  });

  testWidgets('without a pending entry or request the save has no source', (tester) async {
    final store = InMemoryCreationStore();

    await _pump(tester, store: store);

    expect((await store.list('user-1')).single.source, isNull);
  });

  group('Edit prompt', () {
    testWidgets('is shown for a custom prompt and not for a template', (tester) async {
      await _pump(tester, lastRequest: _promptRequest());
      expect(find.text('Edit prompt'), findsOneWidget);

      await tester.pumpWidget(const SizedBox());
      await _pump(tester, lastRequest: _request());
      expect(find.text('Edit prompt'), findsNothing);
    });

    testWidgets('is shown after a failure too', (tester) async {
      final client = FakeApiClient()
        ..onStatus = (id) async =>
            GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed');
      await _pump(tester, client: client, lastRequest: _promptRequest());

      expect(find.text('Edit prompt'), findsOneWidget);
      expect(find.text('Try again'), findsOneWidget);
    });

    testWidgets('opens the form with the photo and prompt and submits nothing', (tester) async {
      final client = FakeApiClient()..onStatus = (id) async => _succeeded(id);
      final request = _promptRequest();
      await _pump(tester, client: client, lastRequest: request);

      await tester.tap(find.text('Edit prompt'));
      await tester.pumpAndSettle();

      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'astronaut on a beach');
      final container = ProviderScope.containerOf(tester.element(find.byType(PhotoPickerField)));
      expect(container.read(selectedPhotoProvider), same(request.photo));
      expect(client.submitted, isEmpty);
    });

    testWidgets('Back returns to the status screen', (tester) async {
      await _pump(tester, lastRequest: _promptRequest());
      await tester.tap(find.text('Edit prompt'));
      await tester.pumpAndSettle();

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.text('Generation Status'), findsOneWidget);
      expect(find.text('Edit prompt'), findsOneWidget);
    });

    testWidgets('survives characters that need URL escaping', (tester) async {
      const prompt = 'a & b #1 100% \u{1F680}';
      await _pump(tester, lastRequest: _promptRequest(prompt));

      await tester.tap(find.text('Edit prompt'));
      await tester.pumpAndSettle();

      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, prompt);
    });

    testWidgets('submitting an edited prompt opens a new status with the new prompt',
        (tester) async {
      final client = FakeApiClient();
      client.onStatus = (id) async => _succeeded(id);
      client.onSubmit = (_) async => 'job-2';
      final request = _promptRequest();
      await _pump(tester, client: client, lastRequest: request);
      await tester.tap(find.text('Edit prompt'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'astronaut on the moon');
      await tester.pump();
      await tester.tap(find.text('Generate'));
      await tester.pumpAndSettle();

      expect(client.submitted.single.prompt, 'astronaut on the moon');
      expect(client.submitted.single.photo, same(request.photo));
      expect(client.statusCalls, contains('job-2'));
      expect(find.text('Generation Status'), findsOneWidget);
    });
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

  testWidgets('a failed status check does not offer Try again or Edit prompt', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (_) async => throw DioException(
            requestOptions: RequestOptions(path: '/generations/job-1'),
            message: 'connection error',
          );
    await _pump(tester, client: client, lastRequest: _promptRequest());

    expect(find.textContaining('Could not reach the server'), findsOneWidget);
    expect(find.text('Try again'), findsNothing);
    expect(find.text('Edit prompt'), findsNothing);
    expect(find.text('New Generation'), findsOneWidget);
  });

  testWidgets('a request from another job is not used as the saved source', (tester) async {
    final store = InMemoryCreationStore();
    final request = GenerationRequest(
      photo: XFile.fromData(tinyPng, name: 'me.png'),
      prompt: 'someone else',
    );
    await _pump(tester, store: store, jobId: 'job-2', lastRequest: request);

    final saved = (await store.list('user-1')).single;
    expect(saved.jobId, 'job-2');
    expect(saved.source, isNull);
  });

  testWidgets('no action is offered on a job the last request did not create', (tester) async {
    final client = FakeApiClient()
      ..onStatus = (id) async =>
          GenerationJob(jobId: id, status: JobStatus.failed, error: 'pipeline_failed');
    await _pump(tester, client: client, lastRequest: _request(), jobId: 'job-9');

    expect(find.text(_pipelineFailedText), findsOneWidget);
    expect(find.text('pipeline_failed'), findsNothing);
    expect(find.text('Try again'), findsNothing);
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

  group('expiry note', () {
    FakeApiClient clientWith(DateTime? expiresAt) => FakeApiClient()
      ..onStatus = (id) async => _succeeded(id, expiresAt: expiresAt);

    testWidgets('a saved result shows the reassuring note', (tester) async {
      await _pump(tester, client: clientWith(_expiry));

      expect(
        find.textContaining(
          'Saved to My creations on this device. Our copy is deleted on',
        ),
        findsOneWidget,
      );
    });

    testWidgets('an unsaved result shows the warning', (tester) async {
      final store = InMemoryCreationStore()..saveError = StateError('disk full');

      await _pump(tester, client: clientWith(_expiry), store: store);

      expect(find.textContaining('Not saved on this device. Download or share it before'),
          findsOneWidget);
      expect(find.textContaining("when it's deleted."), findsOneWidget);
      expect(find.textContaining('Saved to My creations'), findsNothing);
    });

    testWidgets('no note while the save is in progress', (tester) async {
      final store = _SlowStore();

      await _pump(tester, client: clientWith(_expiry), store: store);
      expect(find.textContaining('deleted'), findsNothing);

      store.release.complete();
      await tester.pumpAndSettle();
      expect(find.textContaining('Our copy is deleted on'), findsOneWidget);
    });

    testWidgets('no expires_at means no note and the actions stay', (tester) async {
      await _pump(tester, client: clientWith(null));

      expect(find.textContaining('deleted'), findsNothing);
      expect(find.byType(Image, skipOffstage: false), findsOneWidget);
      expect(find.text('Download'), findsOneWidget);
      expect(find.text('Share'), findsOneWidget);
      expect(find.text('Report'), findsOneWidget);
    });

    testWidgets('the time is shown in the device time zone (+05:30)', (tester) async {
      await _pump(
        tester,
        client: clientWith(_expiry),
        toLocal: (utc) => utc.add(const Duration(hours: 5, minutes: 30)),
      );

      expect(find.textContaining('Fri, Oct 23, 3:30 PM'), findsOneWidget);
    });
  });
}
