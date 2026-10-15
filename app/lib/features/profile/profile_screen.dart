import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../schemas/account.dart';
import '../../schemas/session.dart';
import '../auth/session_notifier.dart';
import '../common/error_message.dart';
import '../plans/account_notifier.dart';
import 'profile_providers.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  @override
  void initState() {
    super.initState();
    // Usage may have changed since the account was last loaded.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(accountProvider.notifier).refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final email = ref.watch(sessionProvider).valueOrNull?.email ?? '';
    final links = ref.watch(profileLinksProvider);
    final version = ref.watch(appVersionProvider).valueOrNull;
    final account = ref.watch(accountProvider).valueOrNull;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        leading: BackButton(
          onPressed: () => context.canPop() ? context.pop() : context.go('/'),
        ),
      ),
      body: ListView(
        children: [
          _Header(email: email),
          if (account?.usage != null) _PlanCard(account: account!),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.card_giftcard),
            title: const Text('Invite friends'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/invite'),
          ),
          if (links.supportEmail != null)
            _LinkTile(
              icon: Icons.help_outline,
              label: 'Help and feedback',
              uri: Uri(scheme: 'mailto', path: links.supportEmail),
            ),
          if (links.privacyUrl != null)
            _LinkTile(
              icon: Icons.privacy_tip_outlined,
              label: 'Privacy policy',
              uri: Uri.parse(links.privacyUrl!),
            ),
          if (links.termsUrl != null)
            _LinkTile(
              icon: Icons.description_outlined,
              label: 'Terms',
              uri: Uri.parse(links.termsUrl!),
            ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Log out'),
            onTap: () => _confirmLogOut(context, ref),
          ),
          ListTile(
            leading: Icon(
              Icons.delete_forever_outlined,
              color: Theme.of(context).colorScheme.error,
            ),
            title: Text(
              'Delete account',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            onTap: () => _confirmDelete(context, ref),
          ),
          if (version != null)
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                'Version $version',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _confirmLogOut(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Log out?'),
        content: const Text('You will need to sign in again to use the app.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Log out'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(sessionProvider.notifier).signOut();
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final password = await showDialog<String>(
      context: context,
      builder: (_) => const _DeleteAccountDialog(),
    );
    if (password == null) return;
    try {
      await ref
          .read(sessionProvider.notifier)
          .deleteAccount(password: password);
    } catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(describeError(error))));
    }
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({required this.account});

  final UserProfile account;

  @override
  Widget build(BuildContext context) {
    final usage = account.usage!;
    final isFree = account.plan == Plan.free;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              isFree ? 'Free plan' : 'Premium plan',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text('${usage.usedToday} of ${usage.dailyLimit} used today'),
            Text('${usage.bonusCredits} bonus credits'),
            if (isFree) ...[
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () => context.push('/upgrade'),
                child: const Text('Upgrade'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.email});

  final String email;

  @override
  Widget build(BuildContext context) {
    final initial = email.isEmpty ? '?' : email[0].toUpperCase();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Column(
        children: [
          CircleAvatar(radius: 36, child: Text(initial, style: const TextStyle(fontSize: 28))),
          const SizedBox(height: 12),
          Text(email, style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}

class _LinkTile extends ConsumerWidget {
  const _LinkTile({required this.icon, required this.label, required this.uri});

  final IconData icon;
  final String label;
  final Uri uri;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListTile(
      leading: Icon(icon),
      title: Text(label),
      trailing: const Icon(Icons.open_in_new, size: 18),
      onTap: () => _open(context, ref),
    );
  }

  Future<void> _open(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    var opened = false;
    try {
      opened = await ref.read(linkLauncherProvider).open(uri);
    } catch (_) {
      opened = false;
    }
    if (!opened) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not open the link.')),
      );
    }
  }
}

class _DeleteAccountDialog extends StatefulWidget {
  const _DeleteAccountDialog();

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
          TextField(
            controller: _password,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Password',
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
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
          onPressed: _password.text.isEmpty
              ? null
              : () => Navigator.of(context).pop(_password.text),
          child: const Text('Delete account'),
        ),
      ],
    );
  }
}
