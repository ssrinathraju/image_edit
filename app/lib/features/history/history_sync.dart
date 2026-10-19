import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';

import '../../schemas/creation.dart';
import '../../schemas/job.dart';
import '../../schemas/session.dart';
import '../../services/generation_providers.dart';
import '../../services/generation_service.dart';
import '../auth/session_notifier.dart';
import '../common/clock.dart';
import 'creation_store.dart';

final _log = Logger('HistorySync');

/// The server deletes results after this long, so waiting longer is pointless.
const Duration pendingGenerationLifetime = Duration(hours: 24);

const int _notFound = 404;

/// Saves the results of generations that finished while the app was not
/// watching them. One run at a time; it never throws.
class HistorySync {
  HistorySync({
    required this.store,
    required this.service,
    required this.clock,
  });

  final CreationStore store;
  final GenerationService service;
  final DateTime Function() clock;

  Future<void>? _running;

  /// Checks the account's unsaved generations; a call during a run joins it.
  Future<void> run(String userId) {
    return _running ??= _runOnce(userId).whenComplete(() => _running = null);
  }

  Future<void> _runOnce(String userId) async {
    try {
      final pending = await store.pending(userId);
      for (final entry in pending) {
        final shouldContinue = await _catchUp(userId, entry);
        if (!shouldContinue) return;
      }
    } on Object catch (error) {
      _log.warning('run_failed ${error.runtimeType}');
    }
  }

  /// Returns false when the run should stop (offline or signed out).
  Future<bool> _catchUp(String userId, PendingGeneration entry) async {
    final age = clock().difference(entry.submittedAt);
    if (age > pendingGenerationLifetime) {
      await store.forget(userId, entry.jobId);
      return true;
    }
    final GenerationJob job;
    try {
      job = await service.getStatus(entry.jobId);
    } on DioException catch (error) {
      return _handleStatusError(userId, entry, error);
    } on Object catch (error) {
      _log.warning('status_failed job=${entry.jobId} ${error.runtimeType}');
      return true;
    }
    return switch (job.status) {
      JobStatus.succeeded => _saveResult(userId, entry, job),
      JobStatus.failed => _forgetAndContinue(userId, entry),
      JobStatus.queued || JobStatus.running => true,
    };
  }

  Future<bool> _handleStatusError(
    String userId,
    PendingGeneration entry,
    DioException error,
  ) async {
    final code = error.response?.statusCode;
    if (code == _notFound) return _forgetAndContinue(userId, entry);
    // A 401 signs the user out elsewhere; anything else means the device is
    // probably offline. Either way the rest waits for the next visit.
    _log.info('status_unavailable job=${entry.jobId} code=${code ?? error.type.name}');
    return false;
  }

  Future<bool> _forgetAndContinue(String userId, PendingGeneration entry) async {
    await store.forget(userId, entry.jobId);
    return true;
  }

  Future<bool> _saveResult(
    String userId,
    PendingGeneration entry,
    GenerationJob job,
  ) async {
    final url = job.resultUrl;
    if (url == null) return true;
    try {
      final bytes = await service.fetchImageBytes(url);
      await store.save(
        userId: userId,
        jobId: entry.jobId,
        label: entry.label,
        bytes: bytes,
        finishedAt: clock(),
      );
      return true;
    } on DioException catch (error) {
      _log.info('image_unavailable job=${entry.jobId} ${error.type.name}');
      return false;
    } on Object catch (error) {
      _log.warning('save_failed job=${entry.jobId} ${error.runtimeType}');
      return true;
    }
  }
}

final historySyncProvider = Provider<HistorySync>(
  (ref) => HistorySync(
    store: ref.watch(creationStoreProvider),
    service: ref.watch(generationServiceProvider),
    clock: ref.watch(clockProvider),
  ),
);

/// Starts a catch-up for the signed-in account and does not wait for it.
void startHistoryCatchUp(WidgetRef ref) {
  unawaited(_catchUpOnceSessionKnown(
    ref.read(sessionProvider.future),
    ref.read(historySyncProvider),
  ));
}

Future<void> _catchUpOnceSessionKnown(
  Future<Session?> sessionFuture,
  HistorySync sync,
) async {
  try {
    final session = await sessionFuture;
    if (session != null) await sync.run(session.userId);
  } on Object catch (error) {
    _log.warning('catch_up_not_started ${error.runtimeType}');
  }
}
