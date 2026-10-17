import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../configs/app_config.dart';
import 'credentials_form.dart';
import 'provider_buttons.dart';
import 'session_notifier.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  bool _providerBusy = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CredentialsForm(
                  submitLabel: 'Create account',
                  enabled: !_providerBusy,
                  passwordError: (password) =>
                      password.length < AppConfig.minPasswordChars
                          ? 'At least ${AppConfig.minPasswordChars} characters'
                          : null,
                  withReferralCode: true,
                  onSubmit: (email, password, referralCode) => ref
                      .read(sessionProvider.notifier)
                      .register(
                        email: email,
                        password: password,
                        referralCode: referralCode.isEmpty ? null : referralCode,
                      ),
                ),
                ProviderButtons(
                  onBusyChanged: (busy) {
                    if (mounted) setState(() => _providerBusy = busy);
                  },
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => context.go('/login'),
                  child: const Text('I already have an account'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
