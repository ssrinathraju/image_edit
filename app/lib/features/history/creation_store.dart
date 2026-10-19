import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';
import 'package:path_provider/path_provider.dart';

import '../../schemas/creation.dart';
import 'backup_exclusion.dart';

final _log = Logger('CreationStore');

const int maxCreationsPerAccount = 50;

const String _creationsFolder = 'creations';
const String _indexFile = 'index.json';
const String _pendingFile = 'pending.json';
const String _tombstoneFile = 'deleted.json';
const String _imageExtension = '.png';
const String _tempExtension = '.tmp';

/// The on-device record of finished generations, one folder per account.
/// Every operation runs on one queue, so two callers saving the same job
/// cannot interleave.
class CreationStore extends ChangeNotifier {
  CreationStore({required this.resolveRoot, required this.backup});

  final Future<Directory> Function() resolveRoot;
  final BackupExclusion backup;

  Future<void> _tail = Future<void>.value();
  Future<Directory>? _ready;

  /// The account's creations, newest first; unreadable data reads as empty.
  Future<List<Creation>> list(String userId) => _run(() => _readIndex(userId));

  /// The folder holding the account's image files, as `<jobId>.png`.
  Future<Directory> accountDirectory(String userId) =>
      _run(() async => _accountDir(userId));

  /// The stored image bytes; throws if the file is missing or unreadable.
  Future<Uint8List> readImage(String userId, String jobId) =>
      _run(() => _imageFile(userId, jobId).readAsBytes());

  /// Saves a creation once per job, drops its pending entry, and keeps only
  /// the newest [maxCreationsPerAccount].
  Future<void> save({
    required String userId,
    required String jobId,
    required String label,
    required Uint8List bytes,
    required DateTime finishedAt,
  }) => _run(() async {
    final dir = await _createAccountDir(userId);
    final index = await _readIndex(userId);
    if (!index.any((c) => c.jobId == jobId)) {
      await _writeAtomic(_imageFile(userId, jobId), bytes);
      index.add(Creation(jobId: jobId, label: label, finishedAt: finishedAt));
      index.sort((a, b) => b.finishedAt.compareTo(a.finishedAt));
      if (index.length > maxCreationsPerAccount) {
        index.removeRange(maxCreationsPerAccount, index.length);
      }
      await _writeJson(File('${dir.path}/$_indexFile'), [
        for (final c in index) c.toJson(),
      ]);
    }
    await _dropPending(userId, jobId);
    await _sweepStrayFiles(dir, index);
    notifyListeners();
  });

  /// Removes a creation and its image file.
  Future<void> delete(String userId, String jobId) => _run(() async {
    final index = await _readIndex(userId);
    index.removeWhere((c) => c.jobId == jobId);
    await _writeJson(File('${_accountDir(userId).path}/$_indexFile'), [
      for (final c in index) c.toJson(),
    ]);
    await _deleteFileIfPresent(_imageFile(userId, jobId));
    notifyListeners();
  });

  /// Records a submitted job so a later catch-up can save its result.
  Future<void> remember({
    required String userId,
    required String jobId,
    required String label,
    required DateTime submittedAt,
  }) => _run(() async {
    final dir = await _createAccountDir(userId);
    final pending = await _readPending(userId);
    if (pending.any((p) => p.jobId == jobId)) return;
    pending.add(
      PendingGeneration(jobId: jobId, label: label, submittedAt: submittedAt),
    );
    await _writeJson(File('${dir.path}/$_pendingFile'), [
      for (final p in pending) p.toJson(),
    ]);
  });

  /// The submitted jobs not saved yet, oldest first.
  Future<List<PendingGeneration>> pending(String userId) =>
      _run(() => _readPending(userId));

  /// Stops tracking a submitted job.
  Future<void> forget(String userId, String jobId) =>
      _run(() => _dropPending(userId, jobId));

  /// Removes everything the account has on the device. A tombstone written
  /// first lets the next start finish the job if this one is interrupted.
  Future<void> deleteAccount(String userId) => _run(() async {
    final tombstones = await _readTombstones();
    if (!tombstones.contains(userId)) {
      await _writeStrings(_tombstones, [...tombstones, userId]);
    }
    await _deleteAccountFolder(userId);
    final remaining = await _readTombstones();
    remaining.remove(userId);
    await _writeStrings(_tombstones, remaining);
    notifyListeners();
  });

  Future<T> _run<T>(Future<T> Function() operation) {
    final result = _tail.then((_) => _ensureReady()).then((_) => operation());
    _tail = result.then<void>((_) {}, onError: (_) {});
    return result;
  }

  Future<Directory> _ensureReady() async {
    final ready = _ready ??= _prepare();
    try {
      return await ready;
    } on Object {
      // A failed start is tried again by the next operation.
      _ready = null;
      rethrow;
    }
  }

  late Directory _creationsDir;

  Future<Directory> _prepare() async {
    final root = await resolveRoot();
    _creationsDir = Directory('${root.path}/$_creationsFolder');
    await _creationsDir.create(recursive: true);
    await _excludeFromBackup();
    await _finishInterruptedDeletions();
    return _creationsDir;
  }

  Future<void> _excludeFromBackup() async {
    try {
      await backup.excludeFromBackup(_creationsDir.path);
    } on Object catch (error) {
      _log.warning('backup_exclusion_failed ${error.runtimeType}');
    }
  }

  Future<void> _finishInterruptedDeletions() async {
    final tombstones = await _readTombstones();
    final failed = <String>[];
    for (final userId in tombstones) {
      try {
        await _deleteAccountFolder(userId);
      } on Object catch (error) {
        failed.add(userId);
        _log.warning('account_cleanup_failed ${error.runtimeType}');
      }
    }
    if (tombstones.isNotEmpty) await _writeStrings(_tombstones, failed);
  }

  File get _tombstones => File('${_creationsDir.path}/$_tombstoneFile');

  Directory _accountDir(String userId) =>
      Directory('${_creationsDir.path}/$userId');

  Future<Directory> _createAccountDir(String userId) =>
      _accountDir(userId).create(recursive: true);

  File _imageFile(String userId, String jobId) =>
      File('${_accountDir(userId).path}/$jobId$_imageExtension');

  Future<void> _deleteAccountFolder(String userId) async {
    final dir = _accountDir(userId);
    if (await dir.exists()) await dir.delete(recursive: true);
  }

  Future<List<Creation>> _readIndex(String userId) => _readJsonList(
    File('${_accountDir(userId).path}/$_indexFile'),
    Creation.fromJson,
  );

  Future<List<PendingGeneration>> _readPending(String userId) => _readJsonList(
    File('${_accountDir(userId).path}/$_pendingFile'),
    PendingGeneration.fromJson,
  );

  Future<void> _dropPending(String userId, String jobId) async {
    final pending = await _readPending(userId);
    if (!pending.any((p) => p.jobId == jobId)) return;
    pending.removeWhere((p) => p.jobId == jobId);
    await _writeJson(File('${_accountDir(userId).path}/$_pendingFile'), [
      for (final p in pending) p.toJson(),
    ]);
  }

  Future<List<String>> _readTombstones() async {
    final file = _tombstones;
    try {
      if (!await file.exists()) return [];
      return [
        for (final id in jsonDecode(await file.readAsString()) as List<dynamic>)
          id as String,
      ];
    } on Object catch (error) {
      _log.warning('tombstone_unreadable ${error.runtimeType}');
      return [];
    }
  }

  Future<List<T>> _readJsonList<T>(
    File file,
    T Function(Map<String, dynamic>) fromJson,
  ) async {
    try {
      if (!await file.exists()) return [];
      final decoded = jsonDecode(await file.readAsString()) as List<dynamic>;
      return [
        for (final item in decoded) fromJson(item as Map<String, dynamic>),
      ];
    } on Object catch (error) {
      _log.warning(
        '${file.uri.pathSegments.last}_unreadable ${error.runtimeType}',
      );
      return [];
    }
  }

  Future<void> _writeJson(File file, List<Map<String, dynamic>> items) =>
      _writeAtomic(file, utf8.encode(jsonEncode(items)));

  Future<void> _writeStrings(File file, List<String> values) =>
      _writeAtomic(file, utf8.encode(jsonEncode(values)));

  Future<void> _writeAtomic(File target, List<int> bytes) async {
    final temp = File('${target.path}$_tempExtension');
    await temp.writeAsBytes(bytes, flush: true);
    await temp.rename(target.path);
  }

  Future<void> _deleteFileIfPresent(File file) async {
    if (await file.exists()) await file.delete();
  }

  /// Removes image files the index does not list (left by a crash or by
  /// eviction) and half-written temp files. Failing here never fails a save.
  Future<void> _sweepStrayFiles(Directory dir, List<Creation> index) async {
    final keep = {for (final c in index) '${c.jobId}$_imageExtension'};
    try {
      await for (final entity in dir.list()) {
        if (entity is! File) continue;
        final name = entity.uri.pathSegments.last;
        final isStrayImage =
            name.endsWith(_imageExtension) && !keep.contains(name);
        if (isStrayImage || name.endsWith(_tempExtension)) {
          await entity.delete();
        }
      }
    } on Object catch (error) {
      _log.warning('sweep_failed ${error.runtimeType}');
    }
  }
}

final creationStoreProvider = Provider<CreationStore>((ref) {
  final store = CreationStore(
    resolveRoot: getApplicationSupportDirectory,
    backup: ref.watch(backupExclusionProvider),
  );
  ref.onDispose(store.dispose);
  return store;
});

/// The signed-in account's creations; refreshes whenever the store changes.
final creationsProvider = FutureProvider.autoDispose
    .family<List<Creation>, String>((ref, userId) {
      final store = ref.watch(creationStoreProvider);
      void refresh() => ref.invalidateSelf();
      store.addListener(refresh);
      ref.onDispose(() => store.removeListener(refresh));
      return store.list(userId);
    });
