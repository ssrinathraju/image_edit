import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../schemas/job.dart';
import 'generation_status_notifier.dart';

class GenerationStatusScreen extends ConsumerWidget {
  const GenerationStatusScreen({required this.jobId, super.key});

  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncJob = ref.watch(generationStatusProvider(jobId));

    return Scaffold(
      appBar: AppBar(title: const Text('Generation Status')),
      body: asyncJob.when(
        loading: () => const _ProgressView(message: 'Starting…'),
        error: (e, _) => _ErrorView(
          message: e.toString(),
          onRetry: () => context.go('/'),
        ),
        data: (job) => switch (job.status) {
          JobStatus.queued => const _ProgressView(message: 'Queued…'),
          JobStatus.running => const _ProgressView(message: 'Generating…'),
          JobStatus.succeeded => _SuccessView(resultUrl: job.resultUrl ?? ''),
          JobStatus.failed => _ErrorView(
              message: job.error ?? 'Generation failed',
              onRetry: () => context.go('/'),
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

class _SuccessView extends StatelessWidget {
  const _SuccessView({required this.resultUrl});

  final String resultUrl;

  @override
  Widget build(BuildContext context) {
    return Image.network(
      resultUrl,
      fit: BoxFit.contain,
      loadingBuilder: (_, child, progress) => progress == null
          ? child
          : const Center(child: CircularProgressIndicator()),
      errorBuilder: (_, _, _) =>
          const Center(child: Text('Could not load image')),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

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
            FilledButton(
              onPressed: onRetry,
              child: const Text('New Generation'),
            ),
          ],
        ),
      ),
    );
  }
}
