import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Explains that the daily limit is reached and offers the two ways out.
/// The screen underneath is left alone, so the photo and prompt stay put.
Future<void> showLimitReachedDialog(BuildContext context, {DateTime? resetsAt}) {
  return showDialog<void>(
    context: context,
    builder: (dialogContext) {
      final reset = resetsAt == null
          ? 'tomorrow'
          : _describeReset(dialogContext, resetsAt.toLocal());
      return AlertDialog(
        title: const Text('Daily limit reached'),
        content: Text(
          "You've used all of today's generations. They reset $reset.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Close'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              context.push('/invite');
            },
            child: const Text('Invite friends'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              context.push('/upgrade');
            },
            child: const Text('Upgrade'),
          ),
        ],
      );
    },
  );
}

String _describeReset(BuildContext context, DateTime local) {
  final time = MaterialLocalizations.of(context)
      .formatTimeOfDay(TimeOfDay.fromDateTime(local));
  return 'at $time';
}
