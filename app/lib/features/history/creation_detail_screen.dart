import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logging/logging.dart';

import '../../schemas/creation.dart';
import '../auth/session_notifier.dart';
import '../common/image_action_row.dart';
import 'creation_store.dart';

final _log = Logger('CreationDetail');

const String _unlabelled = 'Creation';
const String _unavailableMessage = 'This image is no longer available';

typedef _CreationKey = ({String userId, String jobId});

final _creationBytesProvider =
    FutureProvider.autoDispose.family<Uint8List, _CreationKey>(
  (ref, key) =>
      ref.read(creationStoreProvider).readImage(key.userId, key.jobId),
);

class CreationDetailScreen extends ConsumerStatefulWidget {
  const CreationDetailScreen({required this.jobId, super.key});

  final String jobId;

  @override
  ConsumerState<CreationDetailScreen> createState() =>
      _CreationDetailScreenState();
}

class _CreationDetailScreenState extends ConsumerState<CreationDetailScreen> {
  bool _isDeleting = false;

  @override
  Widget build(BuildContext context) {
    final userId = ref.watch(sessionProvider).valueOrNull?.userId;
    return Scaffold(
      appBar: AppBar(title: const Text('Creation')),
      body: userId == null || _isDeleting
          ? const Center(child: CircularProgressIndicator())
          : _body(userId),
    );
  }

  Widget _body(String userId) {
    final key = (userId: userId, jobId: widget.jobId);
    final bytes = ref.watch(_creationBytesProvider(key));
    final creation = ref
        .watch(creationsProvider(userId))
        .valueOrNull
        ?.where((c) => c.jobId == widget.jobId)
        .firstOrNull;
    return bytes.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, _) => _UnavailableView(onDelete: () => _confirmDelete(userId)),
      data: (data) => _DetailBody(
        jobId: widget.jobId,
        bytes: data,
        creation: creation,
        onDelete: () => _confirmDelete(userId),
      ),
    );
  }

  Future<void> _confirmDelete(String userId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete this creation?'),
        content: const Text('It will be removed from this device.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _delete(userId);
  }

  Future<void> _delete(String userId) async {
    final store = ref.read(creationStoreProvider);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    setState(() => _isDeleting = true);
    try {
      await store.delete(userId, widget.jobId);
      router.pop();
    } on Object catch (error) {
      _log.warning('delete_failed job=${widget.jobId} ${error.runtimeType}');
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not delete the creation.')),
      );
      if (mounted) setState(() => _isDeleting = false);
    }
  }
}

class _DetailBody extends StatelessWidget {
  const _DetailBody({
    required this.jobId,
    required this.bytes,
    required this.creation,
    required this.onDelete,
  });

  final String jobId;
  final Uint8List bytes;
  final Creation? creation;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final label = creation?.label ?? '';
    final finishedAt = creation?.finishedAt.toLocal();
    final localizations = MaterialLocalizations.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Image.memory(bytes, fit: BoxFit.contain, width: double.infinity),
        const SizedBox(height: 16),
        Text(
          label.isEmpty ? _unlabelled : label,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (finishedAt != null)
          Text(
            '${localizations.formatMediumDate(finishedAt)}, '
            '${localizations.formatTimeOfDay(TimeOfDay.fromDateTime(finishedAt))}',
          ),
        const SizedBox(height: 16),
        ImageActionRow(bytes: bytes, name: jobId),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: onDelete,
          icon: const Icon(Icons.delete_outline),
          label: const Text('Delete'),
        ),
      ],
    );
  }
}

class _UnavailableView extends StatelessWidget {
  const _UnavailableView({required this.onDelete});

  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.broken_image_outlined, size: 48),
          const SizedBox(height: 12),
          const Text(_unavailableMessage),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: onDelete,
            icon: const Icon(Icons.delete_outline),
            label: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
