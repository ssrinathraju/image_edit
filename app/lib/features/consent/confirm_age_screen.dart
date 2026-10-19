import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_errors.dart';
import '../plans/account_notifier.dart';
import 'age_messages.dart';
import 'date_of_birth_field.dart';

const String _confirmFailedMessage = "Couldn't confirm, try again";

/// Shown before anything else to a signed-in account whose age is not confirmed.
class ConfirmAgeScreen extends ConsumerStatefulWidget {
  const ConfirmAgeScreen({super.key});

  @override
  ConsumerState<ConfirmAgeScreen> createState() => _ConfirmAgeScreenState();
}

class _ConfirmAgeScreenState extends ConsumerState<ConfirmAgeScreen> {
  DateTime? _dateOfBirth;
  bool _submitting = false;
  String? _failure;

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _failure = null;
    });
    try {
      // The router leaves this screen once the account reads as confirmed.
      await ref.read(accountProvider.notifier).confirmAge(_dateOfBirth!);
    } catch (error) {
      if (!mounted) return;
      if (isUnderAge(error)) {
        context.go('/age-blocked');
        return;
      }
      setState(() {
        _failure = isInvalidDateOfBirth(error)
            ? describeDateOfBirthError(error)
            : _confirmFailedMessage;
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Confirm your age')),
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
                      _dateOfBirth == null || _submitting ? null : _submit,
                  child: _submitting
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Confirm'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
