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
    this.withReferralCode = false,
    this.emailController,
    this.enabled = true,
    this.extraField,
    this.extraFieldReady = true,
    this.describeFailure = describeError,
    super.key,
  });

  /// A field the parent owns, shown below the password (the date of birth).
  final Widget? extraField;

  /// False while the parent's [extraField] still lacks a value; keeps submit disabled.
  final bool extraFieldReady;

  /// Turns a failed submit into the inline message; defaults to the server's own text.
  final String Function(Object error) describeFailure;

  /// Lets the parent read the typed email; the parent owns and disposes it.
  final TextEditingController? emailController;

  /// False while something else on the screen (a provider sign-in) is in flight.
  final bool enabled;

  final String submitLabel;

  /// Receives the trimmed entries; `referralCode` is empty when not shown or blank.
  final Future<void> Function(String email, String password, String referralCode)
      onSubmit;

  /// Shows an optional referral code field below the password.
  final bool withReferralCode;

  /// Returns an inline message for a password that is not acceptable yet.
  final String? Function(String password)? passwordError;

  @override
  State<CredentialsForm> createState() => _CredentialsFormState();
}

class _CredentialsFormState extends State<CredentialsForm> {
  late final TextEditingController _email =
      widget.emailController ?? TextEditingController();
  final _password = TextEditingController();
  final _referral = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    if (widget.emailController == null) _email.dispose();
    _password.dispose();
    _referral.dispose();
    super.dispose();
  }

  String? get _passwordMessage {
    final value = _password.text;
    return value.isEmpty ? null : widget.passwordError?.call(value);
  }

  bool get _canSubmit =>
      widget.enabled &&
      widget.extraFieldReady &&
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
      await widget.onSubmit(
        _email.text.trim(),
        _password.text,
        _referral.text.trim(),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _failure = widget.describeFailure(error));
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
        if (widget.extraField != null) ...[
          const SizedBox(height: 12),
          widget.extraField!,
        ],
        if (widget.withReferralCode) ...[
          const SizedBox(height: 12),
          TextField(
            controller: _referral,
            autocorrect: false,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
              labelText: 'Referral code (optional)',
              border: OutlineInputBorder(),
            ),
          ),
        ],
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
