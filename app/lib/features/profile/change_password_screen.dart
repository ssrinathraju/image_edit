import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../configs/app_config.dart';
import '../../core/reauth.dart';
import '../../services/generation_providers.dart';
import '../plans/account_notifier.dart';
import 'reauth.dart';

const String _passwordChangedMessage =
    'Password changed. Other devices were signed out.';

/// Sets or changes the password: the new one is typed here, then the user
/// confirms it is them. A failure keeps what was typed.
class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  ConsumerState<ChangePasswordScreen> createState() =>
      _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> {
  final _password = TextEditingController();
  bool _submitting = false;
  String? _failure;

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  String? get _passwordMessage {
    final value = _password.text;
    if (value.isEmpty || value.length >= AppConfig.minPasswordChars) return null;
    return 'At least ${AppConfig.minPasswordChars} characters';
  }

  bool get _canSubmit =>
      !_submitting && _password.text.length >= AppConfig.minPasswordChars;

  Future<void> _submit() async {
    final account = ref.read(accountProvider).valueOrNull;
    if (account == null) return;
    final api = ref.read(apiClientProvider);
    final accounts = ref.read(accountProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    Reauth? reauth;
    setState(() => _failure = null);
    try {
      reauth = await requestReauth(context, ref, account);
      if (reauth == null || !mounted) return;
      setState(() => _submitting = true);
      await api.changePassword(newPassword: _password.text, reauth: reauth);
      messenger.showSnackBar(const SnackBar(content: Text(_passwordChangedMessage)));
      if (mounted) context.pop();
      // Reloading the account re-runs the router's redirect; in the same frame as
      // the pop it leaves this screen on the stack, so it waits for the next frame.
      WidgetsBinding.instance.addPostFrameCallback((_) => accounts.refresh());
    } catch (error) {
      if (mounted) setState(() => _failure = describeSecurityError(error, reauth));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasPassword = ref.watch(accountProvider).valueOrNull?.hasPassword ?? true;
    final title = hasPassword ? 'Change password' : 'Set a password';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Other devices will be signed out when the password changes.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
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
                      : Text(title),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
