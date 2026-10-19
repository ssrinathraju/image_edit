import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session_notifier.dart';
import '../plans/account_notifier.dart';
import '../profile/delete_account_flow.dart';

const String ageBlockedMessage =
    "This account can't be used because you must be 18 or older.";

/// The end of the line for an account whose owner said they are under 18.
class AgeBlockedScreen extends ConsumerStatefulWidget {
  const AgeBlockedScreen({super.key});

  @override
  ConsumerState<AgeBlockedScreen> createState() => _AgeBlockedScreenState();
}

class _AgeBlockedScreenState extends ConsumerState<AgeBlockedScreen> {
  bool _deleting = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Account unavailable')),
      body: Column(
        children: [
          if (_deleting) const LinearProgressIndicator(),
          Expanded(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(ageBlockedMessage, textAlign: TextAlign.center),
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: _deleting ? null : _delete,
                        child: const Text('Delete account'),
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: _deleting
                            ? null
                            : () => ref.read(sessionProvider.notifier).signOut(),
                        child: const Text('Sign out'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _delete() => runDeleteAccountFlow(
        context,
        ref,
        ref.read(accountProvider).valueOrNull,
        onBusyChanged: (busy) {
          if (mounted) setState(() => _deleting = busy);
        },
      );
}
