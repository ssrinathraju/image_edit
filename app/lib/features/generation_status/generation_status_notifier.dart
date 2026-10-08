import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../schemas/job.dart';
import '../new_generation/new_generation_notifier.dart';

class GenerationStatusNotifier
    extends AutoDisposeFamilyAsyncNotifier<GenerationJob, String> {
  Timer? _timer;

  @override
  Future<GenerationJob> build(String jobId) async {
    ref.onDispose(_cancelTimer);
    return _fetchAndMaybePoll(jobId);
  }

  Future<GenerationJob> _fetchAndMaybePoll(String jobId) async {
    final service = ref.read(generationServiceProvider);
    final job = await service.getStatus(jobId);
    if (!_isTerminal(job.status)) {
      _scheduleNextPoll(jobId);
    }
    return job;
  }

  void _scheduleNextPoll(String jobId) {
    _cancelTimer();
    _timer = Timer(const Duration(seconds: 2), () async {
      try {
        final job = await _fetchAndMaybePoll(jobId);
        state = AsyncData(job);
      } catch (e, st) {
        state = AsyncError(e, st);
      }
    });
  }

  void _cancelTimer() {
    _timer?.cancel();
    _timer = null;
  }

  static bool _isTerminal(JobStatus s) =>
      s == JobStatus.succeeded || s == JobStatus.failed;
}

final generationStatusProvider = AsyncNotifierProvider.autoDispose
    .family<GenerationStatusNotifier, GenerationJob, String>(
      GenerationStatusNotifier.new,
    );
