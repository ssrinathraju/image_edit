import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../plans/account_notifier.dart';
import '../profile/profile_providers.dart';
import 'consent_text.dart';

const String _versionChangedMessage =
    'The consent text changed. Please read it again.';
const String _acceptFailedMessage = "Couldn't save your choice, try again";

/// Asks for face-photo consent. Pops `true` once accepted and `false` when declined.
class ConsentScreen extends ConsumerStatefulWidget {
  const ConsentScreen({super.key});

  @override
  ConsumerState<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends ConsumerState<ConsentScreen> {
  bool _accepting = false;
  String? _failure;

  Future<void> _accept() async {
    setState(() {
      _accepting = true;
      _failure = null;
    });
    try {
      await ref.read(accountProvider.notifier).acceptConsent();
      if (mounted) context.pop(true);
    } catch (error) {
      if (!mounted) return;
      if (isConsentVersionMismatch(error)) {
        await ref.read(accountProvider.notifier).refresh();
      }
      if (!mounted) return;
      setState(() {
        _failure = isConsentVersionMismatch(error)
            ? _versionChangedMessage
            : _acceptFailedMessage;
        _accepting = false;
      });
    }
  }

  Future<void> _openPrivacyPolicy(String url) async {
    final messenger = ScaffoldMessenger.of(context);
    var opened = false;
    try {
      opened = await ref.read(linkLauncherProvider).open(Uri.parse(url));
    } catch (_) {
      opened = false;
    }
    if (!opened) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not open the link.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final consent = ref.watch(accountProvider).valueOrNull?.consent;
    final privacyUrl = ref.watch(profileLinksProvider).privacyUrl;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Face photo consent'),
        leading: BackButton(onPressed: () => context.pop(false)),
      ),
      body: consent == null
          ? _Unavailable(
              onRetry: () => ref.read(accountProvider.notifier).refresh(),
            )
          : _body(context, consent.currentVersion, privacyUrl),
    );
  }

  Widget _body(BuildContext context, String version, String? privacyUrl) {
    final text = consentTextFor(version);
    if (text == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('Update the app to continue', textAlign: TextAlign.center),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(text.intro),
        const SizedBox(height: 16),
        for (final point in text.points)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('\u2022 '),
                Expanded(child: Text(point)),
              ],
            ),
          ),
        if (privacyUrl != null)
          TextButton(
            onPressed: () => _openPrivacyPolicy(privacyUrl),
            child: const Text('Privacy policy'),
          ),
        if (_failure != null) ...[
          const SizedBox(height: 12),
          Text(
            _failure!,
            textAlign: TextAlign.center,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ],
        const SizedBox(height: 20),
        FilledButton(
          onPressed: _accepting ? null : _accept,
          child: _accepting
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Accept'),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: _accepting ? null : () => context.pop(false),
          child: const Text('Decline'),
        ),
      ],
    );
  }
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text("Couldn't load the consent text."),
          const SizedBox(height: 12),
          FilledButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
