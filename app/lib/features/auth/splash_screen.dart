import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'session_notifier.dart';

/// Shown while the saved session is checked at launch.
class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final failed = ref.watch(sessionProvider).hasError;
    return Scaffold(
      body: Center(
        child: failed
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Could not reach the server.'),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed:
                        ref.read(sessionProvider.notifier).retryRestore,
                    child: const Text('Retry'),
                  ),
                ],
              )
            : const CircularProgressIndicator(),
      ),
    );
  }
}
