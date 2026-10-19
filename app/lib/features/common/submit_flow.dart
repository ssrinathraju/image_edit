import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logging/logging.dart';

import '../../core/api_errors.dart';
import '../auth/session_notifier.dart';
import '../history/creation_store.dart';
import '../plans/account_notifier.dart';
import '../plans/limit_reached_dialog.dart';
import 'clock.dart';
import 'error_message.dart';
import 'generation_request.dart';
import 'submit_controller.dart';

final _log = Logger('submit_flow');

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
  final userId = ref.read(sessionProvider).valueOrNull?.userId;
  try {
    final jobId = await ref.read(submitControllerProvider.notifier).submit(request);
    if (userId != null) unawaited(_rememberJob(ref, userId, jobId, request));
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

/// Keeps the job so a later catch-up can save its result. Not awaited by the
/// caller, for the reason the submit flow gives: the store runs its operations
/// in order, so the status screen's save still comes after this. A failure
/// here must not stop the user reaching the status screen.
Future<void> _rememberJob(
  WidgetRef ref,
  String userId,
  String jobId,
  GenerationRequest request,
) async {
  try {
    await ref.read(creationStoreProvider).remember(
          userId: userId,
          jobId: jobId,
          label: request.historyLabel,
          submittedAt: ref.read(clockProvider)(),
        );
  } on Object catch (error) {
    _log.warning('remember_failed job=$jobId ${error.runtimeType}');
  }
}
