import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../core/reauth.dart';
import '../../services/generation_providers.dart';
import '../plans/account_notifier.dart';
import 'email_change_draft.dart';
import 'reauth.dart';

final RegExp _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

const String emailTakenMessage = 'That email is already used by another account';

/// Asks for the new address and confirms the user is them, then sends the code
/// and opens the code step. A failure keeps what was typed.
class ChangeEmailScreen extends ConsumerStatefulWidget {
  const ChangeEmailScreen({super.key});

  @override
  ConsumerState<ChangeEmailScreen> createState() => _ChangeEmailScreenState();
}

class _ChangeEmailScreenState extends ConsumerState<ChangeEmailScreen> {
  final _email = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      !_submitting && _emailPattern.hasMatch(_email.text.trim());

  Future<void> _submit() async {
    final account = ref.read(accountProvider).valueOrNull;
    if (account == null) return;
    final api = ref.read(apiClientProvider);
    final draft = ref.read(emailChangeDraftProvider.notifier);
    final router = GoRouter.of(context);
    final newEmail = _email.text.trim();
    Reauth? reauth;
    setState(() => _failure = null);
    try {
      reauth = await requestReauth(context, ref, account);
      if (reauth == null || !mounted) return;
      setState(() => _submitting = true);
      await api.requestEmailChange(newEmail: newEmail, reauth: reauth);
      draft.state = EmailChangeDraft(newEmail: newEmail, reauth: reauth);
      router.push<void>('/profile/email/confirm');
    } catch (error) {
      if (mounted) setState(() => _failure = _messageFor(error, reauth));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _messageFor(Object error, Reauth? reauth) {
    if (isEmailTaken(error)) return emailTakenMessage;
    if (isTooManyRequests(error)) return tooManyCodesMessage(error);
    return describeSecurityError(error, reauth);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Change email')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  "We'll send a code to the new address. Other devices will be "
                  'signed out when the email changes.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'New email',
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
                  onPressed: _canSubmit ? _submit : null,
                  child: _submitting
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Send code'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// "Too many codes requested", with the wait when the server gave one.
String tooManyCodesMessage(Object error) {
  final wait = retryAfterSecondsOf(error);
  return wait == null
      ? 'Too many codes requested, try later'
      : 'Too many codes requested, try again in ${wait}s';
}
