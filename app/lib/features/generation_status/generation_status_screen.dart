import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logging/logging.dart';

import '../../schemas/job.dart';
import '../auth/session_notifier.dart';
import '../common/clock.dart';
import '../common/error_message.dart';
import '../common/image_action_row.dart';
import '../history/creation_store.dart';
import '../plans/account_notifier.dart';
import '../common/submit_controller.dart';
import '../common/submit_flow.dart';
import 'failure_messages.dart';
import 'generation_status_notifier.dart';
import 'result_image_provider.dart';

final _log = Logger('generation_status');

const String _saveFailedMessage = "Couldn't save to My creations";

class GenerationStatusScreen extends ConsumerWidget {
  const GenerationStatusScreen({required this.jobId, super.key});

  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncJob = ref.watch(generationStatusProvider(jobId));
    // A failed job is refunded, so the remaining count changes.
    ref.listen(generationStatusProvider(jobId), (previous, next) {
      final failedNow = next.valueOrNull?.status == JobStatus.failed;
      final failedBefore = previous?.valueOrNull?.status == JobStatus.failed;
      if (failedNow && !failedBefore) {
        ref.read(accountProvider.notifier).refresh();
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Generation Status')),
      body: asyncJob.when(
        loading: () => const _ProgressView(message: 'Starting…'),
        error: (e, _) =>
            _FailureView(jobId: jobId, message: describeError(e)),
        data: (job) => switch (job.status) {
          JobStatus.queued => const _ProgressView(message: 'Queued…'),
          JobStatus.running => const _ProgressView(message: 'Generating…'),
          JobStatus.succeeded => _SuccessView(job: job),
          JobStatus.failed => _FailureView(
              jobId: jobId,
              message: failureMessageFor(job.error),
            ),
        },
      ),
    );
  }
}

class _ProgressView extends StatelessWidget {
  const _ProgressView({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(message),
        ],
      ),
    );
  }
}

class _SuccessView extends ConsumerWidget {
  const _SuccessView({required this.job});

  final GenerationJob job;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final url = job.resultUrl;
    if (url == null) {
      return _FailureView(jobId: job.jobId, message: 'The image is missing.');
    }
    final bytes = ref.watch(resultImageBytesProvider(url));

    return bytes.when(
      loading: () => const _ProgressView(message: 'Loading image…'),
      error: (_, _) => _FailureView(
        jobId: job.jobId,
        message: 'Could not load the image.',
        onReload: () => ref.invalidate(resultImageBytesProvider(url)),
      ),
      data: (data) => _ResultBody(jobId: job.jobId, bytes: data),
    );
  }
}

class _ResultBody extends ConsumerStatefulWidget {
  const _ResultBody({required this.jobId, required this.bytes});

  final String jobId;
  final Uint8List bytes;

  @override
  ConsumerState<_ResultBody> createState() => _ResultBodyState();
}

class _ResultBodyState extends ConsumerState<_ResultBody> {
  bool _saveStarted = false;

  String get jobId => widget.jobId;
  Uint8List get bytes => widget.bytes;

  // Not initState: a failed save needs the ScaffoldMessenger from context.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_saveStarted) return;
    _saveStarted = true;
    unawaited(_saveToHistory());
  }

  Future<void> _saveToHistory() async {
    // Everything is read before the first await: the user may leave the
    // screen meanwhile, and the bytes in hand should still be saved.
    final messenger = ScaffoldMessenger.of(context);
    final sessionFuture = ref.read(sessionProvider.future);
    final store = ref.read(creationStoreProvider);
    final finishedAt = ref.read(clockProvider)();
    try {
      final session = await sessionFuture;
      if (session == null) return;
      final pending = await store.pending(session.userId);
      final label = pending.where((p) => p.jobId == jobId).firstOrNull?.label ?? '';
      await store.save(
        userId: session.userId,
        jobId: jobId,
        label: label,
        bytes: bytes,
        finishedAt: finishedAt,
      );
    } on Object catch (error) {
      _log.warning('save_failed job=$jobId ${error.runtimeType}');
      messenger.showSnackBar(const SnackBar(content: Text(_saveFailedMessage)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Image.memory(bytes, fit: BoxFit.contain),
        const SizedBox(height: 16),
        ImageActionRow(bytes: bytes, name: jobId, jobId: jobId),
        const SizedBox(height: 12),
        _NavigationButtons(jobId: jobId, homeLabel: 'Home'),
      ],
    );
  }
}

class _FailureView extends StatelessWidget {
  const _FailureView({
    required this.jobId,
    required this.message,
    this.onReload,
  });

  final String jobId;
  final String message;
  final VoidCallback? onReload;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 24),
            if (onReload != null) ...[
              FilledButton(onPressed: onReload, child: const Text('Reload')),
              const SizedBox(height: 12),
            ],
            _NavigationButtons(jobId: jobId, homeLabel: 'New Generation'),
          ],
        ),
      ),
    );
  }
}

class _NavigationButtons extends ConsumerWidget {
  const _NavigationButtons({required this.jobId, required this.homeLabel});

  final String jobId;
  final String homeLabel;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final submitted = ref.watch(lastRequestProvider);
    final lastRequest = submitted?.jobId == jobId ? submitted?.request : null;
    final isSubmitting = ref.watch(submitControllerProvider);
    return Wrap(
      alignment: WrapAlignment.center,
      spacing: 12,
      runSpacing: 12,
      children: [
        if (lastRequest != null)
          FilledButton.icon(
            onPressed: isSubmitting
                ? null
                : () => submitAndOpenStatus(context, ref, lastRequest),
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        FilledButton.tonal(
          onPressed: () {
            ref.read(lastRequestProvider.notifier).state = null;
            context.go('/');
          },
          child: Text(homeLabel),
        ),
      ],
    );
  }
}
