import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'credentials_form.dart';
import 'session_notifier.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  void _openForgotPassword() {
    final typed = _email.text.trim();
    final location = Uri(
      path: '/forgot-password',
      queryParameters: typed.isEmpty ? null : {'email': typed},
    );
    context.push(location.toString());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sign in')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CredentialsForm(
                  submitLabel: 'Sign in',
                  emailController: _email,
                  onSubmit: (email, password, _) => ref
                      .read(sessionProvider.notifier)
                      .signIn(email: email, password: password),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: _openForgotPassword,
                  child: const Text('Forgot password?'),
                ),
                TextButton(
                  onPressed: () => context.go('/register'),
                  child: const Text('Create an account'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
