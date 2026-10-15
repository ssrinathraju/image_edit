import 'package:flutter/material.dart';

import '../common/error_message.dart';

/// Email and password fields with a submit button, shared by sign-in and
/// registration. Submit is disabled while a field is blank or a call is
/// running; failures are shown inline with the server's explanation.
class CredentialsForm extends StatefulWidget {
  const CredentialsForm({
    required this.submitLabel,
    required this.onSubmit,
    this.passwordError,
    super.key,
  });

  final String submitLabel;
  final Future<void> Function(String email, String password) onSubmit;

  /// Returns an inline message for a password that is not acceptable yet.
  final String? Function(String password)? passwordError;

  @override
  State<CredentialsForm> createState() => _CredentialsFormState();
}

class _CredentialsFormState extends State<CredentialsForm> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String? get _passwordMessage {
    final value = _password.text;
    return value.isEmpty ? null : widget.passwordError?.call(value);
  }

  bool get _canSubmit =>
      !_submitting &&
      _email.text.trim().isNotEmpty &&
      _password.text.isNotEmpty &&
      _passwordMessage == null;

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      await widget.onSubmit(_email.text.trim(), _password.text);
    } catch (error) {
      if (!mounted) return;
      setState(() => _failure = describeError(error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          autocorrect: false,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Email',
            border: OutlineInputBorder(),
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _password,
          obscureText: true,
          textInputAction: TextInputAction.done,
          decoration: InputDecoration(
            labelText: 'Password',
            errorText: _passwordMessage,
            border: const OutlineInputBorder(),
          ),
          onChanged: (_) => setState(() {}),
          onSubmitted: (_) {
            if (_canSubmit) _submit();
          },
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
          child: Text(widget.submitLabel),
        ),
      ],
    );
  }
}
