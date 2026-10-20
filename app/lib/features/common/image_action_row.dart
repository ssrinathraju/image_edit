import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/image_actions.dart';
import '../report/report_sheet.dart';

/// Download and Share for an image already in memory (hidden where the
/// platform offers neither, such as web), and Report for the job that made it.
class ImageActionRow extends ConsumerWidget {
  const ImageActionRow({
    required this.bytes,
    required this.name,
    required this.jobId,
    super.key,
  });

  final Uint8List bytes;
  final String name;
  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (ref.watch(showImageActionsProvider)) _saveAndShare(context, ref),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: () => showReportSheet(context, jobId: jobId, bytes: bytes),
            icon: const Icon(Icons.flag_outlined),
            label: const Text('Report'),
          ),
        ),
      ],
    );
  }

  Widget _saveAndShare(BuildContext context, WidgetRef ref) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => _download(context, ref),
            icon: const Icon(Icons.download),
            label: const Text('Download'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Builder(
            builder: (buttonContext) => OutlinedButton.icon(
              onPressed: () => _share(buttonContext, ref),
              icon: const Icon(Icons.share),
              label: const Text('Share'),
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _download(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    String message;
    try {
      final result =
          await ref.read(imageActionsProvider).saveToLibrary(bytes, name: name);
      message = switch (result) {
        SaveResult.saved => 'Saved to your photo library.',
        SaveResult.permissionDenied =>
          'Photo library access is required to save images. '
              'Allow it in Settings and try again.',
      };
    } catch (_) {
      message = 'Could not save the image.';
    }
    messenger.showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _share(BuildContext buttonContext, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(buttonContext);
    final box = buttonContext.findRenderObject() as RenderBox?;
    final origin =
        box == null ? null : box.localToGlobal(Offset.zero) & box.size;
    try {
      await ref
          .read(imageActionsProvider)
          .share(bytes, name: name, origin: origin);
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not open the share sheet.')),
      );
    }
  }
}
