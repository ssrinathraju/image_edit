import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../common/error_message.dart';
import 'code_field.dart';
import 'registration_draft.dart';
import 'resend_code_button.dart';
import 'session_notifier.dart';

const String _invalidCodeMessage = 'Code is incorrect';
const String _expiredCodeMessage = 'Code has expired, tap Resend';
const String _emailTakenMessage = 'Email already registered';

/// Asks for the code emailed at registration. Going back returns to the
/// registration screen underneath, which still holds what was typed.
class ConfirmRegistrationScreen extends ConsumerStatefulWidget {
  const ConfirmRegistrationScreen({super.key});

  @override
  ConsumerState<ConfirmRegistrationScreen> createState() =>
      _ConfirmRegistrationScreenState();
}

class _ConfirmRegistrationScreenState
    extends ConsumerState<ConfirmRegistrationScreen> {
  final _code = TextEditingController();
  bool _submitting = false;
  String? _failure;
  bool _emailTaken = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  bool get _canSubmit => !_submitting && CodeField.isComplete(_code.text);

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _failure = null;
      _emailTaken = false;
    });
    try {
      await ref
          .read(sessionProvider.notifier)
          .confirmRegistration(code: _code.text);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _failure = _messageFor(error);
        _emailTaken = isEmailTaken(error);
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _messageFor(Object error) {
    if (isInvalidCode(error)) return _invalidCodeMessage;
    if (isCodeExpired(error)) return _expiredCodeMessage;
    if (isEmailTaken(error)) return _emailTakenMessage;
    return describeError(error);
  }

  void _goToSignIn() {
    ref.read(registrationDraftProvider.notifier).state = null;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final email = ref.watch(registrationDraftProvider)?.email ?? '';
    return Scaffold(
      appBar: AppBar(title: const Text('Confirm registration')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'We sent a 6-digit code to $email. Enter it to create your account.',
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
                if (_emailTaken)
                  TextButton(
                    onPressed: _goToSignIn,
                    child: const Text('Go to sign-in'),
                  ),
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
                  onResend:
                      ref.read(sessionProvider.notifier).resendRegistrationCode,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
