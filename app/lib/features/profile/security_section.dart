import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../core/provider_sign_in.dart';
import '../../core/reauth.dart';
import '../../schemas/session.dart';
import '../../services/generation_providers.dart';
import '../plans/account_notifier.dart';
import 'reauth.dart';

/// The profile's "Sign-in & security" rows. Hidden until the account has loaded.
class SecuritySection extends ConsumerWidget {
  const SecuritySection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final account = ref.watch(accountProvider).valueOrNull;
    if (account == null) return const SizedBox.shrink();
    final available = {
      SignInProvider.google: ref.watch(isGoogleSignInAvailableProvider),
      SignInProvider.apple: ref.watch(isAppleSignInAvailableProvider),
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: Text(
            'Sign-in & security',
            style: Theme.of(context).textTheme.titleSmall,
          ),
        ),
        ListTile(
          leading: const Icon(Icons.password),
          title: Text(
            account.hasPassword ? 'Change password' : 'Set a password',
          ),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => context.push('/profile/password'),
        ),
        ListTile(
          leading: const Icon(Icons.alternate_email),
          title: const Text('Change email'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => context.push('/profile/email'),
        ),
        for (final provider in SignInProvider.values)
          if (available[provider]!)
            _ProviderRow(
              provider: provider,
              linked: account.providers.contains(provider.apiName),
              account: account,
            ),
        const Divider(),
      ],
    );
  }
}

class _ProviderRow extends ConsumerStatefulWidget {
  const _ProviderRow({
    required this.provider,
    required this.linked,
    required this.account,
  });

  final SignInProvider provider;
  final bool linked;
  final UserProfile account;

  @override
  ConsumerState<_ProviderRow> createState() => _ProviderRowState();
}

class _ProviderRowState extends ConsumerState<_ProviderRow> {
  bool _busy = false;

  SignInProvider get _provider => widget.provider;

  Future<void> _link() async {
    final api = ref.read(apiClientProvider);
    final accounts = ref.read(accountProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    Reauth? reauth;
    try {
      // Prove it is the owner first; the new provider's sheet comes after.
      reauth = await requestReauth(context, ref, widget.account);
      if (reauth == null || !mounted) return;
      setState(() => _busy = true);
      final credential = await ref.read(signInProviderFor(_provider)).signIn();
      if (credential == null) return;
      switch (_provider) {
        case SignInProvider.google:
          await api.linkGoogle(idToken: credential.token, reauth: reauth);
        case SignInProvider.apple:
          await api.linkApple(
            identityToken: credential.token,
            nonce: credential.nonce!,
            authorizationCode: credential.authorizationCode ?? '',
            reauth: reauth,
          );
      }
      await accounts.refresh();
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text(_linkMessage(error, reauth))),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _unlink() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => _UnlinkDialog(provider: _provider),
    );
    if (confirmed != true || !mounted) return;
    final api = ref.read(apiClientProvider);
    final accounts = ref.read(accountProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    Reauth? reauth;
    try {
      reauth = await requestReauth(context, ref, widget.account);
      if (reauth == null || !mounted) return;
      setState(() => _busy = true);
      await api.unlinkProvider(provider: _provider.apiName, reauth: reauth);
      await accounts.refresh();
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text(_unlinkMessage(error, reauth))),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _linkMessage(Object error, Reauth? reauth) {
    final label = _provider.label;
    if (isProviderInUse(error)) {
      return 'That $label account is already linked to a different user.';
    }
    if (isProviderAlreadyLinked(error)) {
      return 'This account already has a $label account linked.';
    }
    if (isInvalidProviderToken(error)) return "Couldn't confirm with $label";
    return describeSecurityError(error, reauth);
  }

  String _unlinkMessage(Object error, Reauth? reauth) {
    if (isLastSignInMethod(error)) {
      return 'Set a password or link another provider first.';
    }
    return describeSecurityError(error, reauth);
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(
        _provider == SignInProvider.google ? Icons.g_mobiledata : Icons.apple,
      ),
      title: Text(_provider.label),
      subtitle: Text(widget.linked ? 'Linked' : 'Not linked'),
      trailing: _busy
          ? const SizedBox(
              height: 18,
              width: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : TextButton(
              onPressed: widget.linked ? _unlink : _link,
              child: Text(widget.linked ? 'Unlink' : 'Link'),
            ),
    );
  }
}

class _UnlinkDialog extends StatelessWidget {
  const _UnlinkDialog({required this.provider});

  final SignInProvider provider;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Unlink ${provider.label}?'),
      content: Text(
        'You will no longer be able to sign in with ${provider.label}. '
        "You'll be asked to confirm it's you.",
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Unlink'),
        ),
      ],
    );
  }
}
