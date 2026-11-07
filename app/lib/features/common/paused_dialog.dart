import 'package:flutter/material.dart';

/// Tells the user generating is paused and when it ends, in local time. The
/// screen underneath is left alone, so the photo and prompt stay put.
Future<void> showPausedDialog(
  BuildContext context, {
  DateTime? until,
  DateTime Function(DateTime) toLocal = _deviceLocal,
}) {
  return showDialog<void>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: const Text('Generating is paused'),
      content: Text(
        'Generating is paused ${_describeEnd(dialogContext, until, toLocal)} '
        'because recent results broke our content rules.',
      ),
      actions: [
        FilledButton(
          onPressed: () => Navigator.of(dialogContext).pop(),
          child: const Text('OK'),
        ),
      ],
    ),
  );
}

DateTime _deviceLocal(DateTime utc) => utc.toLocal();

String _describeEnd(
  BuildContext context,
  DateTime? until,
  DateTime Function(DateTime) toLocal,
) {
  if (until == null) return 'for now';
  final local = toLocal(until);
  final localizations = MaterialLocalizations.of(context);
  final date = localizations.formatMediumDate(local);
  final time = localizations.formatTimeOfDay(TimeOfDay.fromDateTime(local));
  return 'until $date, $time';
}
