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
import 'paused_dialog.dart';
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
  final consent = ref.read(accountProvider).valueOrNull?.consent;
  // Nothing is uploaded before the user has accepted the current consent text.
  if (consent != null &&
      !consent.isCurrentVersionAccepted &&
      !await _askConsent(router)) {
    return;
  }
  try {
    final jobId = await _submitAskingConsentIfRefused(ref, router, account, request);
    if (jobId == null) return;
    if (userId != null) unawaited(_rememberJob(ref, userId, jobId, request));
    router.go('/status/$jobId');
    unawaited(account.refresh());
  } catch (error) {
    // The user may have left while the request was in flight.
    if (!context.mounted) return;
    // The reset time comes from the account as last loaded; it only changes
    // at midnight UTC, so a stale value is still right.
    final resetsAt = ref.read(accountProvider).valueOrNull?.usage?.resetsAt;
    if (isAgeNotConfirmed(error)) {
      // The router keeps the user on the age screen once the account reads as unconfirmed.
      await account.refresh();
      router.go('/confirm-age');
      return;
    }
    unawaited(account.refresh());
    if (isQuotaExceeded(error) && context.mounted) {
      await showLimitReachedDialog(context, resetsAt: resetsAt);
      return;
    }
    if (isGenerationSuspended(error) && context.mounted) {
      await showPausedDialog(context, until: suspendedUntilOf(error));
      return;
    }
    messenger.showSnackBar(SnackBar(content: Text(_submitFailureMessage(error))));
  }
}

const String _promptBlockedMessage = "Your prompt contains words we don't allow.";
const String _photoBlockedMessage = "This photo can't be used. Choose another.";
const String _safetyUnavailableMessage =
    'Checks are unavailable right now, try again.';

/// The app's own wording for the refusals the safety checks produce; anything
/// else falls back to the server's explanation.
String _submitFailureMessage(Object error) {
  if (isPromptBlocked(error)) return _promptBlockedMessage;
  if (isPhotoBlocked(error)) return _photoBlockedMessage;
  if (isSafetyUnavailable(error)) return _safetyUnavailableMessage;
  return describeError(error);
}

Future<bool> _askConsent(GoRouter router) async =>
    await router.push<bool>('/consent') == true;

/// Submits; when the server answers `consent_required` the consent screen opens
/// and, once accepted, the same request is sent one more time. Null means the
/// user declined.
Future<String?> _submitAskingConsentIfRefused(
  WidgetRef ref,
  GoRouter router,
  AccountNotifier account,
  GenerationRequest request,
) async {
  final controller = ref.read(submitControllerProvider.notifier);
  try {
    return await controller.submit(request);
  } catch (error) {
    if (!isConsentRequired(error)) rethrow;
    await account.refresh();
    if (!await _askConsent(router)) return null;
    return controller.submit(request);
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
