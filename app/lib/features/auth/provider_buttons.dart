import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_errors.dart';
import '../../core/provider_sign_in.dart';
import '../common/error_message.dart';
import 'session_notifier.dart';

const String _invalidTokenMessage = 'Sign-in failed, try again';
const String _emailUnverifiedMessage = 'Verify your Google email first';
const String _emailMissingMessage =
    "Apple didn't share an email; remove this app in Apple ID settings and try again";
const String _unavailableMessage = 'Sign-in is unavailable right now';

/// The message for a rejected provider sign-in, falling back to the server's own text.
String describeProviderSignInError(Object error, SignInProvider provider) {
  if (isInvalidProviderToken(error)) return _invalidTokenMessage;
  if (isProviderEmailUnverified(error)) return _emailUnverifiedMessage;
  if (isProviderEmailMissing(error)) return _emailMissingMessage;
  if (isProviderAlreadyLinked(error)) {
    return 'This account is already linked to another ${provider.label} account';
  }
  if (isProviderNotConfigured(error) || isProviderUnavailable(error)) {
    return _unavailableMessage;
  }
  return describeError(error);
}

/// Continue with Google / Apple buttons for the sign-in and register screens.
/// A provider that is not configured on this platform has no button.
class ProviderButtons extends ConsumerStatefulWidget {
  const ProviderButtons({this.onBusyChanged, super.key});

  /// Reports when a sign-in starts and ends, so the screen can lock its other controls.
  final ValueChanged<bool>? onBusyChanged;

  @override
  ConsumerState<ProviderButtons> createState() => _ProviderButtonsState();
}

class _ProviderButtonsState extends ConsumerState<ProviderButtons> {
  SignInProvider? _inFlight;
  String? _failure;

  Future<void> _signIn(SignInProvider provider) async {
    setState(() {
      _inFlight = provider;
      _failure = null;
    });
    widget.onBusyChanged?.call(true);
    try {
      final credential = await ref.read(signInProviderFor(provider)).signIn();
      if (credential == null) return;
      await ref.read(sessionProvider.notifier).signInWithProvider(credential);
    } catch (error) {
      if (!mounted) return;
      setState(() => _failure = describeProviderSignInError(error, provider));
    } finally {
      if (mounted) setState(() => _inFlight = null);
      widget.onBusyChanged?.call(false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final providers = [
      if (ref.watch(isGoogleSignInAvailableProvider)) SignInProvider.google,
      if (ref.watch(isAppleSignInAvailableProvider)) SignInProvider.apple,
    ];
    if (providers.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 16),
        const Row(
          children: [
            Expanded(child: Divider()),
            Padding(padding: EdgeInsets.symmetric(horizontal: 12), child: Text('or')),
            Expanded(child: Divider()),
          ],
        ),
        for (final provider in providers) ...[
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _inFlight == null ? () => _signIn(provider) : null,
            child: _inFlight == provider
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text('Continue with ${provider.label}'),
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
      ],
    );
  }
}
