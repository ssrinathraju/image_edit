import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../../core/provider_sign_in.dart';
import '../auth/provider_buttons.dart';
import '../auth/session_notifier.dart';
import 'age_messages.dart';
import 'date_of_birth_field.dart';

/// What the date-of-birth screen hands back to the sign-in screen when it closes.
enum ProviderAgeOutcome { underAge }

/// Asks a new Google or Apple user for a date of birth and signs in again with
/// the same credential. The credential lives only in this screen's route.
class ProviderAgeScreen extends ConsumerStatefulWidget {
  const ProviderAgeScreen({required this.credential, super.key});

  final ProviderCredential credential;

  @override
  ConsumerState<ProviderAgeScreen> createState() => _ProviderAgeScreenState();
}

class _ProviderAgeScreenState extends ConsumerState<ProviderAgeScreen> {
  DateTime? _dateOfBirth;
  bool _submitting = false;
  String? _failure;

  Future<void> _continue() async {
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      await ref
          .read(sessionProvider.notifier)
          .signInWithProvider(widget.credential, dateOfBirth: _dateOfBirth);
    } catch (error) {
      if (!mounted) return;
      if (isUnderAge(error)) {
        context.pop(ProviderAgeOutcome.underAge);
        return;
      }
      setState(() {
        _failure = isInvalidDateOfBirth(error)
            ? describeDateOfBirthError(error)
            : describeProviderSignInError(error, widget.credential.provider);
        _submitting = false;
      });
      return;
    }
    if (mounted) setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Your date of birth')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'You must be 18 or older to use this app. '
                  'Your date of birth is checked and not stored.',
                ),
                const SizedBox(height: 16),
                DateOfBirthField(
                  value: _dateOfBirth,
                  enabled: !_submitting,
                  onChanged: (date) => setState(() => _dateOfBirth = date),
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
                  onPressed:
                      _dateOfBirth == null || _submitting ? null : _continue,
                  child: _submitting
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Continue'),
                ),
                TextButton(
                  onPressed: _submitting ? null : () => context.pop(),
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
