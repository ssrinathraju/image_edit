import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/history/creation_store.dart';

import '../../support/fake_backup_exclusion.dart';

final _bytes = Uint8List.fromList([1, 2, 3]);

late Directory _root;
late FakeBackupExclusion _backup;

CreationStore _newStore() =>
    CreationStore(resolveRoot: () async => _root, backup: _backup);

Directory _account(String userId) =>
    Directory('${_root.path}/creations/$userId');

List<String> _fileNames(String userId) => _account(userId)
    .listSync()
    .map((e) => e.uri.pathSegments.last)
    .where((name) => name.endsWith('.png'))
    .toList()
  ..sort();

Future<void> _save(
  CreationStore store,
  String jobId, {
  String userId = 'user-1',
  String label = 'a label',
  DateTime? finishedAt,
}) =>
    store.save(
      userId: userId,
      jobId: jobId,
      label: label,
      bytes: _bytes,
      finishedAt: finishedAt ?? DateTime.utc(2026, 10, 19),
    );

void main() {
  setUp(() async {
    _root = await Directory.systemTemp.createTemp('creation_store_test');
    _backup = FakeBackupExclusion();
    addTearDown(() => _root.delete(recursive: true));
  });

  test('save then list returns the newest first', () async {
    final store = _newStore();
    await _save(store, 'monday', finishedAt: DateTime.utc(2026, 10, 19));
    await _save(store, 'tuesday', finishedAt: DateTime.utc(2026, 10, 20));

    final creations = await store.list('user-1');

    expect(creations.map((c) => c.jobId), ['tuesday', 'monday']);
    expect(creations.first.label, 'a label');
    expect(File('${_account('user-1').path}/tuesday.png').readAsBytesSync(), _bytes);
  });

  test('a second save of the same job is a no-op', () async {
    final store = _newStore();
    await _save(store, 'job-1', label: 'first');
    await _save(store, 'job-1', label: 'second');

    final creations = await store.list('user-1');

    expect(creations, hasLength(1));
    expect(creations.single.label, 'first');
  });

  test('two saves of the same job started together create one entry', () async {
    final store = _newStore();

    await Future.wait([_save(store, 'job-1'), _save(store, 'job-1')]);

    expect(await store.list('user-1'), hasLength(1));
  });

  test('the 51st save evicts the oldest entry and its file', () async {
    final store = _newStore();
    for (var i = 0; i < maxCreationsPerAccount; i++) {
      await _save(store, 'job-$i', finishedAt: DateTime.utc(2026, 1, 1).add(Duration(hours: i)));
    }

    await _save(store, 'newest', finishedAt: DateTime.utc(2026, 6, 1));

    final creations = await store.list('user-1');
    expect(creations, hasLength(maxCreationsPerAccount));
    expect(creations.first.jobId, 'newest');
    expect(creations.any((c) => c.jobId == 'job-0'), isFalse);
    expect(File('${_account('user-1').path}/job-0.png').existsSync(), isFalse);
    expect(_fileNames('user-1'), hasLength(maxCreationsPerAccount));
  });

  test('accounts are isolated', () async {
    final store = _newStore();
    await _save(store, 'job-a', userId: 'user-a');
    await _save(store, 'job-b', userId: 'user-b');

    expect((await store.list('user-a')).map((c) => c.jobId), ['job-a']);
    expect((await store.list('user-b')).map((c) => c.jobId), ['job-b']);
    expect(await store.list('user-c'), isEmpty);
  });

  test('delete removes the entry and the file', () async {
    final store = _newStore();
    await _save(store, 'job-1');
    await _save(store, 'job-2');

    await store.delete('user-1', 'job-1');

    expect((await store.list('user-1')).map((c) => c.jobId), ['job-2']);
    expect(File('${_account('user-1').path}/job-1.png').existsSync(), isFalse);
  });

  test('a half-written temp file is ignored', () async {
    final store = _newStore();
    await _save(store, 'job-1');
    File('${_account('user-1').path}/index.json.tmp').writeAsStringSync('[{"jobId":');

    expect((await store.list('user-1')).map((c) => c.jobId), ['job-1']);
  });

  test('an orphan image is removed by the next save', () async {
    final store = _newStore();
    await _save(store, 'job-1');
    File('${_account('user-1').path}/orphan.png').writeAsBytesSync(_bytes);

    await _save(store, 'job-2');

    expect(_fileNames('user-1'), ['job-1.png', 'job-2.png']);
  });

  test('a corrupt index reads as empty', () async {
    final store = _newStore();
    await _save(store, 'job-1');
    File('${_account('user-1').path}/index.json').writeAsStringSync('not json');

    expect(await store.list('user-1'), isEmpty);
  });

  test('remember, pending and forget', () async {
    final store = _newStore();
    final at = DateTime.utc(2026, 10, 19, 7);
    await store.remember(userId: 'user-1', jobId: 'job-1', label: 'one', submittedAt: at);
    await store.remember(userId: 'user-1', jobId: 'job-2', label: 'two', submittedAt: at);
    await store.remember(userId: 'user-1', jobId: 'job-2', label: 'again', submittedAt: at);

    final pending = await store.pending('user-1');
    expect(pending.map((p) => p.jobId), ['job-1', 'job-2']);
    expect(pending.last.label, 'two');
    expect(pending.first.submittedAt, at);
    expect(await store.pending('user-2'), isEmpty);

    await store.forget('user-1', 'job-1');

    expect((await store.pending('user-1')).map((p) => p.jobId), ['job-2']);
  });

  test('save removes the pending entry', () async {
    final store = _newStore();
    await store.remember(
      userId: 'user-1',
      jobId: 'job-1',
      label: 'one',
      submittedAt: DateTime.utc(2026, 10, 19),
    );

    await _save(store, 'job-1');

    expect(await store.pending('user-1'), isEmpty);
  });

  test('readImage returns the stored bytes and throws when the file is gone', () async {
    final store = _newStore();
    await _save(store, 'job-1');

    expect(await store.readImage('user-1', 'job-1'), _bytes);
    File('${_account('user-1').path}/job-1.png').deleteSync();
    await expectLater(store.readImage('user-1', 'job-1'), throwsA(isA<FileSystemException>()));
  });

  test('saving notifies listeners', () async {
    final store = _newStore();
    var notified = 0;
    store.addListener(() => notified++);

    await _save(store, 'job-1');
    await store.delete('user-1', 'job-1');

    expect(notified, 2);
  });

  test('deleteAccount removes the account folder and leaves others alone', () async {
    final store = _newStore();
    await _save(store, 'job-a', userId: 'user-a');
    await _save(store, 'job-b', userId: 'user-b');
    await store.remember(
      userId: 'user-a',
      jobId: 'pending-a',
      label: '',
      submittedAt: DateTime.utc(2026, 10, 19),
    );

    await store.deleteAccount('user-a');

    expect(_account('user-a').existsSync(), isFalse);
    expect(await store.list('user-a'), isEmpty);
    expect(await store.pending('user-a'), isEmpty);
    expect((await store.list('user-b')).map((c) => c.jobId), ['job-b']);
    expect(File('${_root.path}/creations/deleted.json').readAsStringSync(), '[]');
  });

  test('a tombstone left by an interrupted delete is finished at the next start', () async {
    await _save(_newStore(), 'job-a', userId: 'user-a');
    await _save(_newStore(), 'job-b', userId: 'user-b');
    File('${_root.path}/creations/deleted.json').writeAsStringSync(jsonEncode(['user-a']));

    final restarted = _newStore();

    expect(await restarted.list('user-a'), isEmpty);
    expect(_account('user-a').existsSync(), isFalse);
    expect((await restarted.list('user-b')).map((c) => c.jobId), ['job-b']);
    expect(File('${_root.path}/creations/deleted.json').readAsStringSync(), '[]');
  });

  test('the creations folder is excluded from backup when the store starts', () async {
    final store = _newStore();

    await _save(store, 'job-1');
    await _save(store, 'job-2');

    expect(_backup.excluded, ['${_root.path}/creations']);
  });

  test('a failing backup exclusion does not break saving', () async {
    _backup.error = StateError('channel down');
    final store = _newStore();

    await _save(store, 'job-1');

    expect(await store.list('user-1'), hasLength(1));
  });

  test('a start that fails is retried by the next operation', () async {
    var attempts = 0;
    final store = CreationStore(
      resolveRoot: () async {
        if (attempts++ == 0) throw const FileSystemException('not ready');
        return _root;
      },
      backup: _backup,
    );

    await expectLater(store.list('user-1'), throwsA(isA<FileSystemException>()));
    expect(await store.list('user-1'), isEmpty);
  });
}
