import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../configs/app_config.dart';
import '../../core/api_errors.dart';
import '../../services/generation_providers.dart';
import '../common/error_message.dart';
import 'code_field.dart';
import 'resend_code_button.dart';
import 'session_notifier.dart';

const String _rejectedCodeMessage = 'Code is incorrect or has expired';

class ResetPasswordScreen extends ConsumerStatefulWidget {
  const ResetPasswordScreen({required this.email, super.key});

  final String email;

  @override
  ConsumerState<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends ConsumerState<ResetPasswordScreen> {
  final _code = TextEditingController();
  final _password = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    _code.dispose();
    _password.dispose();
    super.dispose();
  }

  String? get _passwordMessage {
    final value = _password.text;
    if (value.isEmpty || value.length >= AppConfig.minPasswordChars) return null;
    return 'At least ${AppConfig.minPasswordChars} characters';
  }

  bool get _canSubmit =>
      !_submitting &&
      CodeField.isComplete(_code.text) &&
      _password.text.length >= AppConfig.minPasswordChars;

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      // Success signs the user in; the router then leaves this screen.
      await ref.read(sessionProvider.notifier).completePasswordReset(
            email: widget.email,
            code: _code.text,
            newPassword: _password.text,
          );
    } catch (error) {
      if (!mounted) return;
      setState(() => _failure =
          isInvalidCode(error) ? _rejectedCodeMessage : describeError(error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reset password')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'If an account exists for ${widget.email}, we sent it a 6-digit code.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                CodeField(controller: _code, onChanged: () => setState(() {})),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: 'New password',
                    errorText: _passwordMessage,
                    border: const OutlineInputBorder(),
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
                      : const Text('Reset password'),
                ),
                const SizedBox(height: 12),
                ResendCodeButton(
                  startCounting: true,
                  onResend: () => ref
                      .read(apiClientProvider)
                      .requestPasswordReset(email: widget.email),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
