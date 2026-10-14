import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../configs/app_config.dart';
import 'credentials_form.dart';
import 'session_notifier.dart';

class RegisterScreen extends ConsumerWidget {
  const RegisterScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
                  passwordError: (password) =>
                      password.length < AppConfig.minPasswordChars
                          ? 'At least ${AppConfig.minPasswordChars} characters'
                          : null,
                  onSubmit: (email, password) => ref
                      .read(sessionProvider.notifier)
                      .register(email: email, password: password),
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
