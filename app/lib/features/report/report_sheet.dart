import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_errors.dart';
import '../../services/generation_providers.dart';

const int maxNoteChars = 500;
const String reportThanksMessage = "Thanks, we'll review it.";
const String _tooManyReportsMessage =
    "You've sent too many reports today. Try again tomorrow.";
const String _sendFailedMessage = "Couldn't send the report. Try again.";

/// The report categories the server accepts, in the order shown.
const List<({String value, String label})> reportCategories = [
  (value: 'sexual', label: 'Sexual content'),
  (value: 'minor', label: 'Involves a minor'),
  (value: 'violence', label: 'Violence or gore'),
  (value: 'hate', label: 'Hateful content'),
  (value: 'other', label: 'Other'),
];

/// Opens the report sheet for the image in [bytes] and, once it was sent,
/// thanks the user. Cancelling sends nothing.
Future<void> showReportSheet(
  BuildContext context, {
  required String jobId,
  required Uint8List bytes,
}) async {
  final messenger = ScaffoldMessenger.of(context);
  final sent = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (_) => ReportSheet(jobId: jobId, bytes: bytes),
  );
  if (sent == true) {
    messenger.showSnackBar(const SnackBar(content: Text(reportThanksMessage)));
  }
}

class ReportSheet extends ConsumerStatefulWidget {
  const ReportSheet({required this.jobId, required this.bytes, super.key});

  final String jobId;
  final Uint8List bytes;

  @override
  ConsumerState<ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends ConsumerState<ReportSheet> {
  final _note = TextEditingController();
  String? _category;
  bool _isSending = false;
  String? _errorMessage;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final category = _category;
    if (category == null || _isSending) return;
    setState(() {
      _isSending = true;
      _errorMessage = null;
    });
    try {
      await ref.read(apiClientProvider).submitReport(
            jobId: widget.jobId,
            category: category,
            note: _note.text.trim(),
            imageBytes: widget.bytes,
          );
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      // The category and note stay as they are, so the user can send again.
      setState(() {
        _isSending = false;
        _errorMessage =
            isTooManyReports(error) ? _tooManyReportsMessage : _sendFailedMessage;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          16,
          16,
          16,
          16 + MediaQuery.of(context).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Report this image',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            RadioGroup<String>(
              groupValue: _category,
              onChanged: (value) {
                if (!_isSending) setState(() => _category = value);
              },
              child: Column(
                children: [
                  for (final category in reportCategories)
                    RadioListTile<String>(
                      value: category.value,
                      title: Text(category.label),
                      enabled: !_isSending,
                      dense: true,
                    ),
                ],
              ),
            ),
            TextField(
              controller: _note,
              enabled: !_isSending,
              maxLength: maxNoteChars,
              maxLines: 3,
              minLines: 1,
              decoration: const InputDecoration(
                labelText: 'Note (optional)',
                border: OutlineInputBorder(),
              ),
            ),
            if (_errorMessage != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  _errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed:
                      _isSending ? null : () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _category == null || _isSending ? null : _send,
                  child: _isSending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Send'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
