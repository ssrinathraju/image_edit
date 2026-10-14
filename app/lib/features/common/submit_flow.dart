import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'error_message.dart';
import 'generation_request.dart';
import 'submit_controller.dart';

/// Submits [request] and opens its status screen; shows a snackbar on failure.
Future<void> submitAndOpenStatus(
  BuildContext context,
  WidgetRef ref,
  GenerationRequest request,
) async {
  final router = GoRouter.of(context);
  final messenger = ScaffoldMessenger.of(context);
  try {
    final jobId = await ref.read(submitControllerProvider.notifier).submit(request);
    router.go('/status/$jobId');
  } catch (error) {
    messenger.showSnackBar(SnackBar(content: Text(describeError(error))));
  }
}
