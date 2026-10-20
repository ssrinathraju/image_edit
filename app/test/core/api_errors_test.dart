import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/api_errors.dart';

DioException _error(Object? data, {int status = 429}) => DioException(
      requestOptions: RequestOptions(path: '/generations'),
      response: Response(
        requestOptions: RequestOptions(path: '/generations'),
        statusCode: status,
        data: data,
      ),
    );

void main() {
  test('extracts quota_exceeded from a 429 response', () {
    final error = _error({
      'detail': {'error': 'quota_exceeded', 'detail': 'limit reached'},
    });

    expect(errorCodeOf(error), 'quota_exceeded');
    expect(isQuotaExceeded(error), isTrue);
  });

  test('other errors have no quota code', () {
    expect(errorCodeOf(_error('plain text')), isNull);
    expect(errorCodeOf(_error({'detail': 'Not Found'}, status: 404)), isNull);
    expect(errorCodeOf(StateError('boom')), isNull);
    expect(
      isQuotaExceeded(_error({'detail': {'error': 'invalid_prompt'}}, status: 400)),
      isFalse,
    );
  });

  test('each registration and reset error code is recognised', () {
    Object coded(String code) => _error({
          'detail': {'error': code, 'detail': 'x'},
        }, status: 400);

    expect(isEmailTaken(coded('email_taken')), isTrue);
    expect(isInvalidCode(coded('invalid_code')), isTrue);
    expect(isCodeExpired(coded('code_expired')), isTrue);
    expect(isTooManyRequests(coded('too_many_requests')), isTrue);
    expect(isInvalidCode(coded('code_expired')), isFalse);
    expect(isTooManyRequests(StateError('boom')), isFalse);
  });

  test('Retry-After is read in seconds and ignored when missing or invalid', () {
    DioException withHeader(String? value) => DioException(
          requestOptions: RequestOptions(path: '/x'),
          response: Response(
            requestOptions: RequestOptions(path: '/x'),
            statusCode: 429,
            headers: Headers.fromMap({
              if (value != null) 'retry-after': [value],
            }),
          ),
        );

    expect(retryAfterSecondsOf(withHeader('40')), 40);
    expect(retryAfterSecondsOf(withHeader(null)), isNull);
    expect(retryAfterSecondsOf(withHeader('soon')), isNull);
    expect(retryAfterSecondsOf(withHeader('0')), isNull);
    expect(retryAfterSecondsOf(StateError('boom')), isNull);
  });

  test('each provider sign-in and referral error code is recognised', () {
    Object coded(String code) => _error({
          'detail': {'error': code, 'detail': 'x'},
        }, status: 400);

    expect(isInvalidProviderToken(coded('invalid_provider_token')), isTrue);
    expect(isProviderEmailUnverified(coded('provider_email_unverified')), isTrue);
    expect(isProviderEmailMissing(coded('provider_email_missing')), isTrue);
    expect(isProviderNotConfigured(coded('provider_not_configured')), isTrue);
    expect(isProviderUnavailable(coded('provider_unavailable')), isTrue);
    expect(isProviderAlreadyLinked(coded('provider_already_linked')), isTrue);
    expect(isReferralNotAllowed(coded('referral_not_allowed')), isTrue);
    expect(isInvalidReferralCode(coded('invalid_referral_code')), isTrue);
    expect(isInvalidProviderToken(coded('provider_unavailable')), isFalse);
    expect(isReferralNotAllowed(StateError('boom')), isFalse);
  });

  test('each age and consent error code is recognised', () {
    Object coded(String code) => _error({
          'detail': {'error': code, 'detail': 'x'},
        }, status: 400);

    expect(isInvalidDateOfBirth(coded('invalid_date_of_birth')), isTrue);
    expect(isUnderAge(coded('under_age')), isTrue);
    expect(isAgeRequired(coded('age_required')), isTrue);
    expect(isAgeAlreadyConfirmed(coded('age_already_confirmed')), isTrue);
    expect(isConsentVersionMismatch(coded('consent_version_mismatch')), isTrue);
    expect(isAgeNotConfirmed(coded('age_not_confirmed')), isTrue);
    expect(isConsentRequired(coded('consent_required')), isTrue);
    expect(isUnderAge(coded('age_required')), isFalse);
    expect(isConsentRequired(StateError('boom')), isFalse);
  });

  test('each safety error code is recognised', () {
    Object coded(String code) => _error({
          'detail': {'error': code, 'detail': 'x'},
        }, status: 400);

    expect(isPromptBlocked(coded('prompt_blocked')), isTrue);
    expect(isPhotoBlocked(coded('photo_blocked')), isTrue);
    expect(isGenerationSuspended(coded('generation_suspended')), isTrue);
    expect(isSafetyUnavailable(coded('safety_unavailable')), isTrue);
    expect(isTooManyReports(coded('too_many_reports')), isTrue);
    expect(isPromptBlocked(coded('photo_blocked')), isFalse);
  });

  test('suspendedUntilOf reads the end of the pause', () {
    final error = _error({
      'detail': {
        'error': 'generation_suspended',
        'detail': 'paused',
        'suspended_until': '2026-10-21T15:05:00+00:00',
      },
    }, status: 403);

    expect(suspendedUntilOf(error), DateTime.utc(2026, 10, 21, 15, 5));
  });

  test('suspendedUntilOf is null without a readable time', () {
    expect(suspendedUntilOf(_error({'detail': {'error': 'generation_suspended'}})), isNull);
    expect(
      suspendedUntilOf(_error({
        'detail': {'suspended_until': 'not a time'},
      })),
      isNull,
    );
    expect(suspendedUntilOf(_error('plain')), isNull);
    expect(suspendedUntilOf(StateError('boom')), isNull);
  });
}
