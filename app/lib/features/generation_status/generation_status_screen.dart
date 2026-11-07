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
import '../common/generation_request.dart';
import '../common/image_action_row.dart';
import '../history/creation_store.dart';
import '../plans/account_notifier.dart';
import '../common/submit_controller.dart';
import '../common/submit_flow.dart';
import 'failure_messages.dart';
import 'generation_status_notifier.dart';
import 'result_image_provider.dart';

final _log = Logger('generation_status');

const String _moreLikeThisLabel = 'More like this';
const String _tryAgainLabel = 'Try again';
const String _editPromptLabel = 'Edit prompt';
const String _saveFailedMessage = "Couldn't save to My creations";

/// Converts the server's UTC expiry to the time shown; replaceable in tests.
final expiryToLocalProvider = Provider<DateTime Function(DateTime)>(
  (_) =>
      (utc) => utc.toLocal(),
);

enum _SaveState { pending, saved, failed }

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
        // The job may still be running, so a second generation is not offered.
        error: (e, _) => _FailureView(
          jobId: jobId,
          message: describeError(e),
          canRetry: false,
        ),
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
      return _FailureView(
        jobId: job.jobId,
        message: 'The image is missing.',
        succeeded: true,
      );
    }
    final bytes = ref.watch(resultImageBytesProvider(url));

    return bytes.when(
      loading: () => const _ProgressView(message: 'Loading image…'),
      error: (_, _) => _FailureView(
        jobId: job.jobId,
        message: 'Could not load the image.',
        succeeded: true,
        // The link may have expired, so ask for status again to get a new one. The
        // bytes are cached per link, so the new link is fetched on its own.
        onReload: () => ref.invalidate(generationStatusProvider(job.jobId)),
      ),
      data: (data) =>
          _ResultBody(jobId: job.jobId, bytes: data, expiresAt: job.expiresAt),
    );
  }
}

class _ResultBody extends ConsumerStatefulWidget {
  const _ResultBody({
    required this.jobId,
    required this.bytes,
    required this.expiresAt,
  });

  final String jobId;
  final Uint8List bytes;
  final DateTime? expiresAt;

  @override
  ConsumerState<_ResultBody> createState() => _ResultBodyState();
}

class _ResultBodyState extends ConsumerState<_ResultBody> {
  bool _saveStarted = false;
  _SaveState _saveState = _SaveState.pending;

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
    final submitted = ref.read(lastRequestProvider);
    final requestSource = submitted?.jobId == jobId
        ? submitted?.request.source
        : null;
    try {
      final session = await sessionFuture;
      if (session == null) {
        _setSaveState(_SaveState.failed);
        return;
      }
      final pending = await store.pending(session.userId);
      final entry = pending.where((p) => p.jobId == jobId).firstOrNull;
      await store.save(
        userId: session.userId,
        jobId: jobId,
        label: entry?.label ?? '',
        bytes: bytes,
        finishedAt: finishedAt,
        source: entry?.source ?? requestSource,
      );
      _setSaveState(_SaveState.saved);
    } on Object catch (error) {
      _log.warning('save_failed job=$jobId ${error.runtimeType}');
      _setSaveState(_SaveState.failed);
      messenger.showSnackBar(const SnackBar(content: Text(_saveFailedMessage)));
    }
  }

  void _setSaveState(_SaveState state) {
    if (mounted) setState(() => _saveState = state);
  }

  @override
  Widget build(BuildContext context) {
    final expiresAt = widget.expiresAt;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Image.memory(bytes, fit: BoxFit.contain),
        if (expiresAt != null && _saveState != _SaveState.pending) ...[
          const SizedBox(height: 12),
          _ExpiryNote(
            saved: _saveState == _SaveState.saved,
            expiresAt: expiresAt,
          ),
        ],
        const SizedBox(height: 16),
        ImageActionRow(bytes: bytes, name: jobId, jobId: jobId),
        const SizedBox(height: 12),
        _NavigationButtons(jobId: jobId, homeLabel: 'Home', succeeded: true),
      ],
    );
  }
}

class _ExpiryNote extends ConsumerWidget {
  const _ExpiryNote({required this.saved, required this.expiresAt});

  final bool saved;
  final DateTime expiresAt;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final local = ref.watch(expiryToLocalProvider)(expiresAt);
    final localizations = MaterialLocalizations.of(context);
    final when =
        '${localizations.formatMediumDate(local)}, '
        '${localizations.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
    final text = saved
        ? 'Saved to My creations on this device. Our copy is deleted on $when.'
        : "Not saved on this device. Download or share it before $when, when it's deleted.";
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          saved ? Icons.check_circle_outline : Icons.warning_amber_rounded,
          size: 18,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text, style: Theme.of(context).textTheme.bodySmall),
        ),
      ],
    );
  }
}

class _FailureView extends StatelessWidget {
  const _FailureView({
    required this.jobId,
    required this.message,
    this.succeeded = false,
    this.canRetry = true,
    this.onReload,
  });

  final String jobId;
  final String message;
  final bool succeeded;

  /// False when the job's outcome is unknown, such as a failed status check.
  final bool canRetry;
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
            _NavigationButtons(
              jobId: jobId,
              homeLabel: 'New Generation',
              succeeded: succeeded,
              canRetry: canRetry,
            ),
          ],
        ),
      ),
    );
  }
}

class _NavigationButtons extends ConsumerWidget {
  const _NavigationButtons({
    required this.jobId,
    required this.homeLabel,
    required this.succeeded,
    this.canRetry = true,
  });

  final String jobId;
  final String homeLabel;
  final bool succeeded;
  final bool canRetry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final submitted = ref.watch(lastRequestProvider);
    final lastRequest = canRetry && submitted?.jobId == jobId
        ? submitted?.request
        : null;
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
            label: Text(succeeded ? _moreLikeThisLabel : _tryAgainLabel),
          ),
        if (lastRequest?.prompt != null)
          OutlinedButton.icon(
            onPressed: isSubmitting
                ? null
                : () => _editPrompt(context, lastRequest!),
            icon: const Icon(Icons.edit_outlined),
            label: const Text(_editPromptLabel),
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

void _editPrompt(BuildContext context, GenerationRequest request) {
  final location = Uri(
    path: '/create',
    queryParameters: {'prompt': request.prompt},
  ).toString();
  unawaited(context.push<void>(location, extra: request.photo));
}
