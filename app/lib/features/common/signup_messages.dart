import '../../core/api_errors.dart';

const String disposableEmailMessage = 'Use a permanent email address.';

const int _secondsPerMinute = 60;

/// "Too many new accounts from this network", with the wait from `Retry-After`
/// in minutes (rounded up) from a minute on, otherwise in seconds.
String tooManySignupsMessage(Object error) {
  const prefix = 'Too many new accounts from this network.';
  final wait = retryAfterSecondsOf(error);
  if (wait == null) return '$prefix Try again later.';
  if (wait < _secondsPerMinute) {
    return '$prefix Try again in $wait ${wait == 1 ? 'second' : 'seconds'}.';
  }
  final minutes = (wait / _secondsPerMinute).ceil();
  return '$prefix Try again in $minutes ${minutes == 1 ? 'minute' : 'minutes'}.';
}

/// The message for a refused sign-up, or null when the error is not one of them.
String? describeSignupRefusal(Object error) {
  if (isDisposableEmail(error)) return disposableEmailMessage;
  if (isTooManySignups(error)) return tooManySignupsMessage(error);
  return null;
}
