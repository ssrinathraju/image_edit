import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../services/generation_providers.dart';
import '../common/error_message.dart';
import '../plans/account_notifier.dart';
import 'session_notifier.dart';

const String _unknownCodeMessage = 'Code not recognised';
const String _notAllowedMessage = "This account can't redeem a code";

/// Shown once after a provider sign-in created the account; Skip and Apply both end at home.
class ReferralPromptScreen extends ConsumerStatefulWidget {
  const ReferralPromptScreen({super.key});

  @override
  ConsumerState<ReferralPromptScreen> createState() =>
      _ReferralPromptScreenState();
}

class _ReferralPromptScreenState extends ConsumerState<ReferralPromptScreen> {
  final _code = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void initState() {
    super.initState();
    ref.read(sessionProvider.notifier).takeJustCreatedViaProvider();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  bool get _canApply => !_submitting && _code.text.trim().isNotEmpty;

  Future<void> _apply() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      await ref
          .read(apiClientProvider)
          .redeemReferral(code: _code.text.trim());
      await ref.read(accountProvider.notifier).refresh();
      if (mounted) context.go('/');
    } catch (error) {
      if (!mounted) return;
      if (isReferralNotAllowed(error)) {
        messenger.showSnackBar(const SnackBar(content: Text(_notAllowedMessage)));
        context.go('/');
        return;
      }
      setState(() => _failure = _messageFor(error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _messageFor(Object error) =>
      isInvalidReferralCode(error) ? _unknownCodeMessage : describeError(error);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Welcome')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Have a referral code?',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Enter a friend\'s code and you both get bonus generations.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _code,
                  autocorrect: false,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                    labelText: 'Referral code',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (_) => setState(() {}),
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
                  onPressed: _canApply ? _apply : null,
                  child: _submitting
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Apply'),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: _submitting ? null : () => context.go('/'),
                  child: const Text('Skip'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
