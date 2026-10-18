import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../configs/app_config.dart';
import '../../core/api_errors.dart';
import '../common/error_message.dart';
import 'credentials_form.dart';
import 'provider_buttons.dart';
import 'session_notifier.dart';

const String _emailTakenMessage = 'Email already registered';
const String _unknownReferralMessage = 'Code not recognised';

String _describeRegistrationError(Object error) {
  if (isEmailTaken(error)) return _emailTakenMessage;
  if (isInvalidReferralCode(error)) return _unknownReferralMessage;
  if (isTooManyRequests(error)) {
    final wait = retryAfterSecondsOf(error);
    return wait == null
        ? 'Too many codes requested, try again later'
        : 'Too many codes requested, try again in $wait s';
  }
  return describeError(error);
}

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  bool _providerBusy = false;

  Future<void> _startRegistration(
    String email,
    String password,
    String referralCode,
  ) async {
    await ref.read(sessionProvider.notifier).startRegistration(
          email: email,
          password: password,
          referralCode: referralCode.isEmpty ? null : referralCode,
        );
    // Pushed, not gone to, so Back returns here with the values kept.
    if (mounted) unawaited(context.push('/confirm-registration'));
  }

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
                  describeFailure: _describeRegistrationError,
                  onSubmit: _startRegistration,
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
