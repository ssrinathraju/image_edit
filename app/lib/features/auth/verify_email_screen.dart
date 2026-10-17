import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../services/generation_providers.dart';
import '../common/error_message.dart';
import '../plans/account_notifier.dart';
import 'code_field.dart';
import 'resend_code_button.dart';
import 'session_notifier.dart';

const String _invalidCodeMessage = 'Code is incorrect';
const String _expiredCodeMessage = 'Code has expired, tap Resend';

class VerifyEmailScreen extends ConsumerStatefulWidget {
  const VerifyEmailScreen({super.key});

  @override
  ConsumerState<VerifyEmailScreen> createState() => _VerifyEmailScreenState();
}

class _VerifyEmailScreenState extends ConsumerState<VerifyEmailScreen> {
  final _code = TextEditingController();
  late final bool _justRegistered;
  bool _submitting = false;
  String? _failure;

  @override
  void initState() {
    super.initState();
    _justRegistered = ref.read(sessionProvider.notifier).takeJustRegistered();
  }

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
    });
    try {
      await ref.read(apiClientProvider).verifyEmail(code: _code.text);
      await _finish();
    } catch (error) {
      if (!mounted) return;
      if (isAlreadyVerified(error)) return _finish();
      setState(() => _failure = _messageFor(error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _finish() async {
    await ref.read(accountProvider.notifier).refresh();
    if (mounted) _leave(context);
  }

  String _messageFor(Object error) {
    if (isInvalidCode(error)) return _invalidCodeMessage;
    if (isCodeExpired(error)) return _expiredCodeMessage;
    return describeError(error);
  }

  @override
  Widget build(BuildContext context) {
    final email = ref.watch(sessionProvider).valueOrNull?.email ?? '';
    return Scaffold(
      appBar: AppBar(title: const Text('Verify email')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'We sent a 6-digit code to $email. Enter it to verify your email.',
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
                      : const Text('Verify'),
                ),
                const SizedBox(height: 12),
                ResendCodeButton(
                  startCounting: _justRegistered,
                  onResend: ref.read(apiClientProvider).resendVerification,
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => _leave(context),
                  child: const Text('Later'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Returns to the screen underneath (a form that must keep its input, or
/// home); right after registration there is none, so go home.
void _leave(BuildContext context) {
  if (context.canPop()) {
    context.pop();
  } else {
    context.go('/');
  }
}
