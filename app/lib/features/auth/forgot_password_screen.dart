import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../services/generation_providers.dart';
import '../common/error_message.dart';

const String _invalidEmailMessage = 'Email address is not valid';
const String _invalidFormatCode = 'invalid_credentials_format';

class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({this.initialEmail = '', super.key});

  final String initialEmail;

  @override
  ConsumerState<ForgotPasswordScreen> createState() =>
      _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  late final TextEditingController _email =
      TextEditingController(text: widget.initialEmail);
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  bool get _canSubmit => !_submitting && _email.text.trim().isNotEmpty;

  Future<void> _submit() async {
    final email = _email.text.trim();
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      await ref.read(apiClientProvider).requestPasswordReset(email: email);
      if (!mounted) return;
      final next = Uri(path: '/reset-password', queryParameters: {'email': email});
      await context.push(next.toString());
    } catch (error) {
      if (!mounted) return;
      setState(() => _failure = errorCodeOf(error) == _invalidFormatCode
          ? _invalidEmailMessage
          : describeError(error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Forgot password')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Enter your email and we will send you a code to reset your password.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Email',
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
