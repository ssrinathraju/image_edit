import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../plans/account_notifier.dart';
import '../plans/limit_reached_dialog.dart';
import 'error_message.dart';
import 'generation_request.dart';
import 'submit_controller.dart';

/// Submits [request] and opens its status screen. A refused request shows a
/// snackbar, or the limit dialog when the daily allowance is used up; the
/// caller's photo and prompt are never touched.
///
/// The account reload is never awaited before the UI reacts: once the submit
/// call returns the form is enabled again, so anything slow here would leave a
/// window for a second tap to spend another generation.
Future<void> submitAndOpenStatus(
  BuildContext context,
  WidgetRef ref,
  GenerationRequest request,
) async {
  final router = GoRouter.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final account = ref.read(accountProvider.notifier);
  try {
    final jobId = await ref.read(submitControllerProvider.notifier).submit(request);
    router.go('/status/$jobId');
    unawaited(account.refresh());
  } catch (error) {
    // The user may have left while the request was in flight.
    if (!context.mounted) return;
    // The reset time comes from the account as last loaded; it only changes
    // at midnight UTC, so a stale value is still right.
    final resetsAt = ref.read(accountProvider).valueOrNull?.usage?.resetsAt;
    unawaited(account.refresh());
    if (isQuotaExceeded(error) && context.mounted) {
      await showLimitReachedDialog(context, resetsAt: resetsAt);
      return;
    }
    messenger.showSnackBar(SnackBar(content: Text(describeError(error))));
  }
}
