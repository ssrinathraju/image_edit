import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_errors.dart';
import '../../core/provider_sign_in.dart';
import '../../schemas/session.dart';
import '../auth/session_notifier.dart';
import '../common/error_message.dart';

/// Confirms with the user, then deletes the account: with the password, or for an
/// account without one by signing in with a provider again. [onBusyChanged]
/// reports when the deletion starts and ends. A failure shows a snackbar.
Future<void> runDeleteAccountFlow(
  BuildContext context,
  WidgetRef ref,
  UserProfile? account, {
  required ValueChanged<bool> onBusyChanged,
}) async {
  final messenger = ScaffoldMessenger.of(context);
  final provider = account != null && !account.hasPassword
      ? _providerToConfirmWith(ref, account)
      : null;
  final confirmation = await showDialog<String>(
    context: context,
    builder: (_) => _DeleteAccountDialog(confirmWith: provider),
  );
  // The screen can be gone by now (say the session expired behind the dialog).
  if (confirmation == null || !context.mounted) return;
  onBusyChanged(true);
  try {
    final notifier = ref.read(sessionProvider.notifier);
    if (provider == null) {
      await notifier.deleteAccount(password: confirmation);
    } else {
      final credential = await ref.read(signInProviderFor(provider)).signIn();
      if (credential == null) return;
      await notifier.deleteAccountWithProvider(credential);
    }
  } catch (error) {
    messenger.showSnackBar(
      SnackBar(content: Text(_deleteErrorMessage(error, provider))),
    );
  } finally {
    onBusyChanged(false);
  }
}

/// Apple when the account is linked to it and this is an iPhone, otherwise Google.
SignInProvider _providerToConfirmWith(WidgetRef ref, UserProfile account) {
  final isIos = ref.read(targetPlatformProvider) == TargetPlatform.iOS;
  final hasApple = account.providers.contains(SignInProvider.apple.apiName);
  return hasApple && isIos ? SignInProvider.apple : SignInProvider.google;
}

String _deleteErrorMessage(Object error, SignInProvider? provider) {
  if (provider != null && isInvalidProviderToken(error)) {
    return "Couldn't confirm with ${provider.label}";
  }
  return describeError(error);
}

class _DeleteAccountDialog extends StatefulWidget {
  const _DeleteAccountDialog({this.confirmWith});

  /// Set for an account without a password: it confirms by signing in again with this provider.
  final SignInProvider? confirmWith;

  @override
  State<_DeleteAccountDialog> createState() => _DeleteAccountDialogState();
}

class _DeleteAccountDialogState extends State<_DeleteAccountDialog> {
  final _password = TextEditingController();

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = widget.confirmWith;
    return AlertDialog(
      title: const Text('Delete account?'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'This is permanent. Your account, your sign-ins and your '
            'generated images are deleted and cannot be recovered.',
          ),
          const SizedBox(height: 16),
          if (provider == null)
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Password',
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            )
          else
            Text("You'll be asked to sign in with ${provider.label} again to confirm."),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
          onPressed: provider == null && _password.text.isEmpty
              ? null
              : () => Navigator.of(context).pop(_password.text),
          child: const Text('Delete account'),
        ),
      ],
    );
  }
}
