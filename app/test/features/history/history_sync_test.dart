import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/history/history_sync.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/services/generation_service.dart';

import '../../support/fake_api_client.dart';
import '../../support/in_memory_creation_store.dart';

final _now = DateTime.utc(2026, 10, 19, 12);
final _bytes = Uint8List.fromList([9, 8, 7]);

DioException _dio(int? status) => DioException(
      requestOptions: RequestOptions(path: '/generations/x'),
      type: status == null ? DioExceptionType.connectionError : DioExceptionType.badResponse,
      response: status == null
          ? null
          : Response(requestOptions: RequestOptions(path: '/x'), statusCode: status),
    );

GenerationJob _job(String id, JobStatus status) => GenerationJob(
      jobId: id,
      status: status,
      resultUrl: status == JobStatus.succeeded ? 'http://fake/$id.png' : null,
    );

late FakeApiClient client;
late InMemoryCreationStore store;
late HistorySync sync;

Future<void> _remember(String jobId, {Duration age = const Duration(hours: 1)}) =>
    store.remember(
      userId: 'user-1',
      jobId: jobId,
      label: 'label $jobId',
      submittedAt: _now.subtract(age),
    );

List<String> _pendingIds() =>
    store.pendings['user-1']?.map((p) => p.jobId).toList() ?? [];

void main() {
  setUp(() {
    client = FakeApiClient()..onFetchBytes = (_) async => _bytes;
    store = InMemoryCreationStore();
    sync = HistorySync(
      store: store,
      service: GenerationService(client),
      clock: () => _now,
    );
  });

  test('a succeeded job is saved with its remembered label', () async {
    client.onStatus = (id) async => _job(id, JobStatus.succeeded);
    await _remember('job-1');

    await sync.run('user-1');

    final saved = (await store.list('user-1')).single;
    expect(saved.jobId, 'job-1');
    expect(saved.label, 'label job-1');
    expect(saved.finishedAt, _now);
    expect(await store.readImage('user-1', 'job-1'), _bytes);
    expect(_pendingIds(), isEmpty);
  });

  test('a call for another account does not join a run in flight', () async {
    client.onStatus = (id) async => _job(id, JobStatus.succeeded);
    await _remember('job-1');
    await store.remember(
      userId: 'user-2',
      jobId: 'job-2',
      label: 'label job-2',
      submittedAt: _now.subtract(const Duration(hours: 1)),
    );

    await Future.wait([sync.run('user-1'), sync.run('user-2')]);

    expect((await store.list('user-1')).single.jobId, 'job-1');
    expect((await store.list('user-2')).single.jobId, 'job-2');
  });

  test('a failed job is forgotten and nothing is added', () async {
    client.onStatus = (id) async => _job(id, JobStatus.failed);
    await _remember('job-1');

    await sync.run('user-1');

    expect(await store.list('user-1'), isEmpty);
    expect(_pendingIds(), isEmpty);
  });

  test('a job the server no longer has is forgotten', () async {
    client.onStatus = (_) async => throw _dio(404);
    await _remember('job-1');

    await sync.run('user-1');

    expect(await store.list('user-1'), isEmpty);
    expect(_pendingIds(), isEmpty);
  });

  test('queued and running jobs stay remembered and the run goes on', () async {
    client.onStatus = (id) async => id == 'job-1'
        ? _job(id, JobStatus.running)
        : id == 'job-2'
            ? _job(id, JobStatus.queued)
            : _job(id, JobStatus.succeeded);
    await _remember('job-1');
    await _remember('job-2');
    await _remember('job-3');

    await sync.run('user-1');

    expect(_pendingIds(), ['job-1', 'job-2']);
    expect((await store.list('user-1')).single.jobId, 'job-3');
  });

  test('a job older than 24 hours is forgotten without asking the server', () async {
    await _remember('old', age: const Duration(hours: 24, minutes: 1));

    await sync.run('user-1');

    expect(client.statusCalls, isEmpty);
    expect(_pendingIds(), isEmpty);
  });

  test('a job just inside 24 hours is still checked', () async {
    client.onStatus = (id) async => _job(id, JobStatus.running);
    await _remember('edge', age: const Duration(hours: 23, minutes: 59));

    await sync.run('user-1');

    expect(client.statusCalls, ['edge']);
    expect(_pendingIds(), ['edge']);
  });

  test('a network error keeps the entry and stops the run', () async {
    client.onStatus = (_) async => throw _dio(null);
    await _remember('job-1');
    await _remember('job-2');

    await expectLater(sync.run('user-1'), completes);

    expect(client.statusCalls, ['job-1']);
    expect(_pendingIds(), ['job-1', 'job-2']);
  });

  test('a server error keeps the entry and stops the run', () async {
    client.onStatus = (_) async => throw _dio(503);
    await _remember('job-1');
    await _remember('job-2');

    await sync.run('user-1');

    expect(client.statusCalls, ['job-1']);
    expect(_pendingIds(), ['job-1', 'job-2']);
  });

  test('a 401 stops the run and keeps the entries', () async {
    client.onStatus = (_) async => throw _dio(401);
    await _remember('job-1');
    await _remember('job-2');

    await sync.run('user-1');

    expect(client.statusCalls, ['job-1']);
    expect(_pendingIds(), ['job-1', 'job-2']);
  });

  test('an image-fetch error keeps the entry', () async {
    client.onStatus = (id) async => _job(id, JobStatus.succeeded);
    client.onFetchBytes = (_) async => throw _dio(null);
    await _remember('job-1');

    await expectLater(sync.run('user-1'), completes);

    expect(await store.list('user-1'), isEmpty);
    expect(_pendingIds(), ['job-1']);
  });

  test('two concurrent runs make one set of calls', () async {
    final gate = Completer<GenerationJob>();
    client.onStatus = (_) => gate.future;
    await _remember('job-1');

    final first = sync.run('user-1');
    final second = sync.run('user-1');
    gate.complete(_job('job-1', JobStatus.failed));
    await Future.wait([first, second]);

    expect(client.statusCalls, ['job-1']);
  });

  test('a finished run can be followed by another', () async {
    client.onStatus = (id) async => _job(id, JobStatus.running);
    await _remember('job-1');

    await sync.run('user-1');
    await sync.run('user-1');

    expect(client.statusCalls, ['job-1', 'job-1']);
  });

  test('no error ever reaches the caller', () async {
    client.onStatus = (_) async => throw StateError('unexpected');
    await _remember('job-1');
    await _remember('job-2');

    await expectLater(sync.run('user-1'), completes);

    expect(_pendingIds(), ['job-1', 'job-2']);
  });

  test('a store that fails while saving does not end the run', () async {
    client.onStatus = (id) async => _job(id, JobStatus.succeeded);
    store.saveError = StateError('disk full');
    await _remember('job-1');
    await _remember('job-2');

    await expectLater(sync.run('user-1'), completes);

    expect(client.statusCalls, ['job-1', 'job-2']);
    expect(_pendingIds(), ['job-1', 'job-2']);
  });

  test('only the given account is checked', () async {
    client.onStatus = (id) async => _job(id, JobStatus.failed);
    await _remember('mine');
    await store.remember(
      userId: 'user-2',
      jobId: 'theirs',
      label: '',
      submittedAt: _now,
    );

    await sync.run('user-1');

    expect(client.statusCalls, ['mine']);
    expect(store.pendings['user-2'], hasLength(1));
  });
}
