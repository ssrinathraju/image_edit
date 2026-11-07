import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/api_errors.dart';
import 'package:image_edit/features/common/signup_messages.dart';

import '../../support/app_harness.dart';

Object _tooMany({int? retryAfter}) =>
    apiError(429, 'too_many_signups', 'x', retryAfterSeconds: retryAfter);

void main() {
  test(
    'both new codes are recognised and not confused with the codes message',
    () {
      expect(isDisposableEmail(apiError(400, 'disposable_email', 'x')), isTrue);
      expect(isTooManySignups(_tooMany()), isTrue);
      expect(
        isTooManySignups(apiError(429, 'too_many_requests', 'x')),
        isFalse,
      );
      expect(isDisposableEmail(StateError('boom')), isFalse);
    },
  );

  test('1800 seconds reads 30 minutes', () {
    expect(
      tooManySignupsMessage(_tooMany(retryAfter: 1800)),
      'Too many new accounts from this network. Try again in 30 minutes.',
    );
  });

  test('61 seconds rounds up to 2 minutes', () {
    expect(
      tooManySignupsMessage(_tooMany(retryAfter: 61)),
      'Too many new accounts from this network. Try again in 2 minutes.',
    );
  });

  test('exactly one minute is singular', () {
    expect(
      tooManySignupsMessage(_tooMany(retryAfter: 60)),
      'Too many new accounts from this network. Try again in 1 minute.',
    );
  });

  test('45 seconds reads in seconds', () {
    expect(
      tooManySignupsMessage(_tooMany(retryAfter: 45)),
      'Too many new accounts from this network. Try again in 45 seconds.',
    );
  });

  test('without Retry-After the message still reads well', () {
    expect(
      tooManySignupsMessage(_tooMany()),
      'Too many new accounts from this network. Try again later.',
    );
  });

  test('other errors are not described as refusals', () {
    expect(describeSignupRefusal(apiError(409, 'email_taken', 'x')), isNull);
    expect(
      describeSignupRefusal(apiError(400, 'disposable_email', 'x')),
      'Use a permanent email address.',
    );
  });
}
