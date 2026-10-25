import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_errors.dart';
import '../../core/provider_sign_in.dart';
import '../../core/reauth.dart';
import '../../schemas/session.dart';
import '../common/error_message.dart';

/// Apple when the account is linked to it and this is an iPhone, otherwise Google.
SignInProvider providerToConfirmWith(
  TargetPlatform platform,
  UserProfile account,
) {
  final hasApple = account.providers.contains(SignInProvider.apple.apiName);
  return hasApple && platform == TargetPlatform.iOS
      ? SignInProvider.apple
      : SignInProvider.google;
}

/// Asks the user to prove it is them: the current password for an account
/// that has one, otherwise a fresh sign-in with a linked provider. Null when
/// the user cancels either; nothing is shown then.
Future<Reauth?> requestReauth(
  BuildContext context,
  WidgetRef ref,
  UserProfile account,
) async {
  if (account.hasPassword) {
    final password = await showDialog<String>(
      context: context,
      builder: (_) => const _CurrentPasswordDialog(),
    );
    return password == null ? null : Reauth.password(password);
  }
  final provider =
      providerToConfirmWith(ref.read(targetPlatformProvider), account);
  final credential = await ref.read(signInProviderFor(provider)).signIn();
  return credential == null ? null : Reauth.provider(credential);
}

/// The message for a failed security call; a refused re-authentication says
/// which kind of proof was refused.
String describeSecurityError(Object error, Reauth? reauth) {
  if (isReauthFailed(error)) {
    final provider = reauth?.provider;
    return provider == null
        ? 'Password is incorrect'
        : "Couldn't confirm with ${provider.label}";
  }
  return describeError(error);
}

class _CurrentPasswordDialog extends StatefulWidget {
  const _CurrentPasswordDialog();

  @override
  State<_CurrentPasswordDialog> createState() => _CurrentPasswordDialogState();
}

class _CurrentPasswordDialogState extends State<_CurrentPasswordDialog> {
  final _password = TextEditingController();

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Confirm it’s you'),
      content: TextField(
        controller: _password,
        obscureText: true,
        autofocus: true,
        decoration: const InputDecoration(
          labelText: 'Current password',
          border: OutlineInputBorder(),
        ),
        onChanged: (_) => setState(() {}),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _password.text.isEmpty
              ? null
              : () => Navigator.of(context).pop(_password.text),
          child: const Text('Confirm'),
        ),
      ],
    );
  }
}
