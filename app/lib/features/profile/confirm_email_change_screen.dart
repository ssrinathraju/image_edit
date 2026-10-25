import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../services/generation_providers.dart';
import '../auth/code_field.dart';
import '../auth/resend_code_button.dart';
import '../common/error_message.dart';
import '../plans/account_notifier.dart';
import 'change_email_screen.dart';
import 'email_change_draft.dart';

const String _invalidCodeMessage = 'Code is incorrect';
const String _expiredCodeMessage = 'Code has expired, tap Resend';
const String _emailChangedMessage = 'Email changed. Other devices were signed out.';

/// Asks for the code emailed to the new address. Going back returns to the
/// Change email screen, which still holds what was typed.
class ConfirmEmailChangeScreen extends ConsumerStatefulWidget {
  const ConfirmEmailChangeScreen({super.key});

  @override
  ConsumerState<ConfirmEmailChangeScreen> createState() =>
      _ConfirmEmailChangeScreenState();
}

class _ConfirmEmailChangeScreenState
    extends ConsumerState<ConfirmEmailChangeScreen> {
  final _code = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  bool get _canSubmit => !_submitting && CodeField.isComplete(_code.text);

  Future<void> _submit() async {
    final api = ref.read(apiClientProvider);
    final accounts = ref.read(accountProvider.notifier);
    final draft = ref.read(emailChangeDraftProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      await api.confirmEmailChange(code: _code.text);
      draft.state = null;
      messenger.showSnackBar(const SnackBar(content: Text(_emailChangedMessage)));
      router.go('/profile');
      // Reloading the account re-runs the router's redirect, so it follows the
      // navigation rather than racing it.
      WidgetsBinding.instance.addPostFrameCallback((_) => accounts.refresh());
    } catch (error) {
      if (!mounted) return;
      if (isEmailTaken(error)) return _backToChangeEmail(messenger, router);
      setState(() => _failure = _messageFor(error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _backToChangeEmail(ScaffoldMessengerState messenger, GoRouter router) {
    messenger.showSnackBar(
      const SnackBar(content: Text('$emailTakenMessage. Choose another.')),
    );
    router.pop();
  }

  String _messageFor(Object error) {
    if (isInvalidCode(error)) return _invalidCodeMessage;
    if (isCodeExpired(error)) return _expiredCodeMessage;
    return describeError(error);
  }

  @override
  Widget build(BuildContext context) {
    final draft = ref.watch(emailChangeDraftProvider);
    return PopScope(
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) ref.read(emailChangeDraftProvider.notifier).state = null;
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Confirm new email')),
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'We sent a 6-digit code to ${draft?.newEmail ?? ''}. '
                    'Enter it to change your email.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 20),
                  CodeField(controller: _code, onChanged: () => setState(() {})),
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
                        : const Text('Confirm'),
                  ),
                  const SizedBox(height: 12),
                  ResendCodeButton(
                    startCounting: true,
                    onResend: () {
                      final pending = ref.read(emailChangeDraftProvider);
                      if (pending == null) return Future<void>.value();
                      return ref.read(apiClientProvider).requestEmailChange(
                            newEmail: pending.newEmail,
                            reauth: pending.reauth,
                          );
                    },
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
