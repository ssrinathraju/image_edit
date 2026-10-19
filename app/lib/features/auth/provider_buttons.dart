import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import '../../core/api_errors.dart';
import '../../core/provider_sign_in.dart';
import '../common/error_message.dart';
import '../consent/age_messages.dart';
import '../consent/provider_age_screen.dart';
import 'session_notifier.dart';

const String _invalidTokenMessage = 'Sign-in failed, try again';
const String _emailMissingMessage =
    "Apple didn't share an email; remove this app in Apple ID settings and try again";
const String _unavailableMessage = 'Sign-in is unavailable right now';

/// The message for a rejected provider sign-in, falling back to the server's own text.
String describeProviderSignInError(Object error, SignInProvider provider) {
  if (isInvalidProviderToken(error)) return _invalidTokenMessage;
  if (isProviderEmailUnverified(error)) {
    return 'Verify your ${provider.label} email first';
  }
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
      await _signInOrAskAge(credential);
    } catch (error) {
      if (!mounted) return;
      setState(() => _failure = describeProviderSignInError(error, provider));
    } finally {
      if (mounted) setState(() => _inFlight = null);
      widget.onBusyChanged?.call(false);
    }
  }

  /// A new account must give a date of birth: the age screen signs in again with
  /// the same credential and hands back `underAge` when it was refused.
  Future<void> _signInOrAskAge(ProviderCredential credential) async {
    final notifier = ref.read(sessionProvider.notifier);
    try {
      await notifier.signInWithProvider(credential);
    } catch (error) {
      if (!isAgeRequired(error)) rethrow;
      if (!mounted) return;
      final outcome = await context.push<ProviderAgeOutcome>(
        '/age',
        extra: credential,
      );
      if (outcome == ProviderAgeOutcome.underAge && mounted) {
        setState(() => _failure = underAgeMessage);
      }
    }
  }

  Widget _buttonFor(SignInProvider provider) {
    final onPressed = _inFlight == null ? () => _signIn(provider) : null;
    final label = 'Continue with ${provider.label}';
    if (provider == SignInProvider.apple) {
      return _inFlight == provider
          ? const _AppleBusyButton()
          : SignInWithAppleButton(onPressed: onPressed, text: label);
    }
    return OutlinedButton(
      onPressed: onPressed,
      child: _inFlight == provider
          ? const SizedBox(
              height: 18,
              width: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Text(label),
    );
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
          _buttonFor(provider),
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

/// Apple's black button with a spinner, shown while its sign-in is in flight.
class _AppleBusyButton extends StatelessWidget {
  const _AppleBusyButton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 44,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(8),
      ),
      child: const SizedBox(
        height: 18,
        width: 18,
        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
      ),
    );
  }
}
