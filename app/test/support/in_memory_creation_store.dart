import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/history/creation_store.dart';
import 'package:image_edit/schemas/creation.dart';

import 'fake_backup_exclusion.dart';

/// A [CreationStore] that keeps everything in memory, because real file I/O
/// never completes inside a widget test's fake-async zone. The real store has
/// its own tests; widget tests only need its behaviour as seen by screens.
class InMemoryCreationStore extends CreationStore {
  InMemoryCreationStore()
      : super(
          resolveRoot: () async => Directory.systemTemp,
          backup: FakeBackupExclusion(),
        ) {
    imageDirectory = Directory.systemTemp.createTempSync('in_memory_store');
    addTearDown(() => imageDirectory.deleteSync(recursive: true));
  }

  /// Where [accountDirectory] points; tests write image files here.
  late final Directory imageDirectory;

  final creations = <String, List<Creation>>{};
  final pendings = <String, List<PendingGeneration>>{};
  final images = <String, Uint8List>{};
  final savedJobs = <String>[];
  final deletedAccounts = <String>[];
  Object? saveError;
  Object? deleteAccountError;
  Object? rememberError;

  @override
  Future<List<Creation>> list(String userId) async => [
        ...?creations[userId],
      ]..sort((a, b) => b.finishedAt.compareTo(a.finishedAt));

  @override
  Future<Directory> accountDirectory(String userId) async => imageDirectory;

  @override
  Future<Uint8List> readImage(String userId, String jobId) async {
    final bytes = images['$userId/$jobId'];
    if (bytes == null) throw FileSystemException('missing', jobId);
    return bytes;
  }

  @override
  Future<void> save({
    required String userId,
    required String jobId,
    required String label,
    required Uint8List bytes,
    required DateTime finishedAt,
  }) async {
    if (saveError != null) throw saveError!;
    savedJobs.add(jobId);
    final list = creations.putIfAbsent(userId, () => []);
    if (!list.any((c) => c.jobId == jobId)) {
      list.add(Creation(jobId: jobId, label: label, finishedAt: finishedAt));
      images['$userId/$jobId'] = bytes;
      File('${imageDirectory.path}/$jobId.png').writeAsBytesSync(bytes);
    }
    pendings[userId]?.removeWhere((p) => p.jobId == jobId);
    notifyListeners();
  }

  @override
  Future<void> delete(String userId, String jobId) async {
    creations[userId]?.removeWhere((c) => c.jobId == jobId);
    images.remove('$userId/$jobId');
    final file = File('${imageDirectory.path}/$jobId.png');
    if (file.existsSync()) file.deleteSync();
    notifyListeners();
  }

  @override
  Future<void> remember({
    required String userId,
    required String jobId,
    required String label,
    required DateTime submittedAt,
  }) async {
    if (rememberError != null) throw rememberError!;
    final list = pendings.putIfAbsent(userId, () => []);
    if (list.any((p) => p.jobId == jobId)) return;
    list.add(PendingGeneration(jobId: jobId, label: label, submittedAt: submittedAt));
  }

  @override
  Future<List<PendingGeneration>> pending(String userId) async =>
      [...?pendings[userId]];

  @override
  Future<void> forget(String userId, String jobId) async =>
      pendings[userId]?.removeWhere((p) => p.jobId == jobId);

  @override
  Future<void> deleteAccount(String userId) async {
    deletedAccounts.add(userId);
    if (deleteAccountError != null) throw deleteAccountError!;
    creations.remove(userId);
    pendings.remove(userId);
    notifyListeners();
  }
}
