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
    await account.refresh();
    router.go('/status/$jobId');
  } catch (error) {
    await account.refresh();
    if (isQuotaExceeded(error) && context.mounted) {
      final resetsAt = ref.read(accountProvider).valueOrNull?.usage?.resetsAt;
      await showLimitReachedDialog(context, resetsAt: resetsAt);
      return;
    }
    messenger.showSnackBar(SnackBar(content: Text(describeError(error))));
  }
}
