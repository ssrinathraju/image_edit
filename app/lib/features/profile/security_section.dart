import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/provider_sign_in.dart';
import '../../schemas/session.dart';
import '../plans/account_notifier.dart';

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
          title: Text(account.hasPassword ? 'Change password' : 'Set a password'),
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

class _ProviderRow extends StatelessWidget {
  const _ProviderRow({
    required this.provider,
    required this.linked,
    required this.account,
  });

  final SignInProvider provider;
  final bool linked;
  final UserProfile account;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(
        provider == SignInProvider.google ? Icons.g_mobiledata : Icons.apple,
      ),
      title: Text(provider.label),
      subtitle: Text(linked ? 'Linked' : 'Not linked'),
    );
  }
}
