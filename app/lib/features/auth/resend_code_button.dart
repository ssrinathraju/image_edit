import 'dart:async';

import 'package:flutter/material.dart';

import '../../configs/app_config.dart';
import '../../core/api_errors.dart';
import '../common/error_message.dart';

const String _tooManyCodesMessage = 'Too many codes requested, try later';
const String _sentMessage = 'A new code was sent';

/// Resend action with a countdown. It is disabled while the countdown runs
/// and while a request is in flight, and reports its own outcome underneath.
class ResendCodeButton extends StatefulWidget {
  const ResendCodeButton({
    required this.onResend,
    this.startCounting = false,
    super.key,
  });

  final Future<void> Function() onResend;

  /// Starts the countdown as soon as the button appears, because a code was
  /// just sent.
  final bool startCounting;

  @override
  State<ResendCodeButton> createState() => _ResendCodeButtonState();
}

class _ResendCodeButtonState extends State<ResendCodeButton> {
  Timer? _timer;
  int _secondsLeft = 0;
  bool _sending = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    if (widget.startCounting) _startCountdown(AppConfig.resendCooldownSeconds);
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startCountdown(int seconds) {
    _timer?.cancel();
    setState(() => _secondsLeft = seconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_secondsLeft <= 1) timer.cancel();
      setState(() => _secondsLeft--);
    });
  }

  Future<void> _resend() async {
    setState(() {
      _sending = true;
      _message = null;
    });
    try {
      await widget.onResend();
      if (!mounted) return;
      _startCountdown(AppConfig.resendCooldownSeconds);
      setState(() => _message = _sentMessage);
    } catch (error) {
      if (!mounted) return;
      _showFailure(error);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _showFailure(Object error) {
    if (!isTooManyRequests(error)) {
      setState(() => _message = describeError(error));
      return;
    }
    final wait = retryAfterSecondsOf(error);
    if (wait != null) _startCountdown(wait);
    setState(() {
      _message = wait == null
          ? _tooManyCodesMessage
          : 'Too many codes requested, try again in ${wait}s';
    });
  }

  @override
  Widget build(BuildContext context) {
    final enabled = _secondsLeft == 0 && !_sending;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OutlinedButton(
          onPressed: enabled ? _resend : null,
          child: _sending
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(_secondsLeft > 0 ? 'Resend code in ${_secondsLeft}s' : 'Resend code'),
        ),
        if (_message != null) ...[
          const SizedBox(height: 8),
          Text(_message!, textAlign: TextAlign.center),
        ],
      ],
    );
  }
}
