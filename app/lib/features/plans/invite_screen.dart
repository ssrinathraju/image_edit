import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../configs/app_config.dart';
import 'account_notifier.dart';

typedef ShareText = Future<void> Function(String text, {Rect? origin});

final shareTextProvider = Provider<ShareText>(
  (_) => (text, {origin}) async {
    await SharePlus.instance.share(
      ShareParams(text: text, sharePositionOrigin: origin),
    );
  },
);

final inviteUrlProvider = Provider<String?>((_) => AppConfig.inviteUrl);

/// The message friends receive; the link is included only when configured.
String inviteMessage(String code, String? inviteUrl) {
  final base = 'Join me on image edit! Use my code $code when you sign up.';
  return inviteUrl == null ? base : '$base\n$inviteUrl';
}

class InviteScreen extends ConsumerWidget {
  const InviteScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final referral = ref.watch(accountProvider).valueOrNull?.referral;
    return Scaffold(
      appBar: AppBar(title: const Text('Invite friends')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: referral == null
            ? const Center(child: Text('Invites are not available right now.'))
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Give friends ${referral.bonusPerReferral} bonus generations '
                    'and get ${referral.bonusPerReferral} yourself when they '
                    'sign up with your code.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  Center(
                    child: SelectableText(
                      referral.code,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${referral.rewards} of ${referral.maxRewards} friends rewarded',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  Builder(
                    builder: (buttonContext) => FilledButton.icon(
                      onPressed: () => _share(buttonContext, ref, referral.code),
                      icon: const Icon(Icons.share),
                      label: const Text('Share'),
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  Future<void> _share(BuildContext context, WidgetRef ref, String code) async {
    final messenger = ScaffoldMessenger.of(context);
    final box = context.findRenderObject() as RenderBox?;
    final origin = box == null ? null : box.localToGlobal(Offset.zero) & box.size;
    try {
      await ref.read(shareTextProvider)(
        inviteMessage(code, ref.read(inviteUrlProvider)),
        origin: origin,
      );
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not open the share sheet.')),
      );
    }
  }
}
