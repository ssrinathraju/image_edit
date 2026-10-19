import 'package:dio/dio.dart';

/// The server's machine-readable error code (`detail.error`), if it sent one.
String? errorCodeOf(Object error) {
  if (error is! DioException) return null;
  final data = error.response?.data;
  if (data is! Map) return null;
  final detail = data['detail'];
  if (detail is! Map) return null;
  final code = detail['error'];
  return code is String ? code : null;
}

/// Seconds from the `Retry-After` header of a failed response, if it sent one.
int? retryAfterSecondsOf(Object error) {
  if (error is! DioException) return null;
  final value = error.response?.headers.value('retry-after');
  final seconds = value == null ? null : int.tryParse(value);
  return seconds != null && seconds > 0 ? seconds : null;
}

const String quotaExceededCode = 'quota_exceeded';

bool isQuotaExceeded(Object error) => errorCodeOf(error) == quotaExceededCode;

const String invalidCodeCode = 'invalid_code';
const String codeExpiredCode = 'code_expired';
const String emailTakenCode = 'email_taken';
const String registrationChangedCode = 'registration_changed';
const String tooManyRequestsCode = 'too_many_requests';

bool isInvalidCode(Object error) => errorCodeOf(error) == invalidCodeCode;
bool isCodeExpired(Object error) => errorCodeOf(error) == codeExpiredCode;
bool isEmailTaken(Object error) => errorCodeOf(error) == emailTakenCode;
bool isRegistrationChanged(Object error) =>
    errorCodeOf(error) == registrationChangedCode;
bool isTooManyRequests(Object error) => errorCodeOf(error) == tooManyRequestsCode;

const String invalidProviderTokenCode = 'invalid_provider_token';
const String providerEmailUnverifiedCode = 'provider_email_unverified';
const String providerEmailMissingCode = 'provider_email_missing';
const String providerNotConfiguredCode = 'provider_not_configured';
const String providerUnavailableCode = 'provider_unavailable';
const String providerAlreadyLinkedCode = 'provider_already_linked';
const String referralNotAllowedCode = 'referral_not_allowed';
const String invalidReferralCodeCode = 'invalid_referral_code';

const String invalidDateOfBirthCode = 'invalid_date_of_birth';
const String underAgeCode = 'under_age';
const String ageRequiredCode = 'age_required';
const String ageAlreadyConfirmedCode = 'age_already_confirmed';
const String consentVersionMismatchCode = 'consent_version_mismatch';
const String ageNotConfirmedCode = 'age_not_confirmed';
const String consentRequiredCode = 'consent_required';

bool isInvalidDateOfBirth(Object error) =>
    errorCodeOf(error) == invalidDateOfBirthCode;
bool isUnderAge(Object error) => errorCodeOf(error) == underAgeCode;
bool isAgeRequired(Object error) => errorCodeOf(error) == ageRequiredCode;
bool isAgeAlreadyConfirmed(Object error) =>
    errorCodeOf(error) == ageAlreadyConfirmedCode;
bool isConsentVersionMismatch(Object error) =>
    errorCodeOf(error) == consentVersionMismatchCode;
bool isAgeNotConfirmed(Object error) =>
    errorCodeOf(error) == ageNotConfirmedCode;
bool isConsentRequired(Object error) =>
    errorCodeOf(error) == consentRequiredCode;

bool isInvalidProviderToken(Object error) =>
    errorCodeOf(error) == invalidProviderTokenCode;
bool isProviderEmailUnverified(Object error) =>
    errorCodeOf(error) == providerEmailUnverifiedCode;
bool isProviderEmailMissing(Object error) =>
    errorCodeOf(error) == providerEmailMissingCode;
bool isProviderNotConfigured(Object error) =>
    errorCodeOf(error) == providerNotConfiguredCode;
bool isProviderUnavailable(Object error) =>
    errorCodeOf(error) == providerUnavailableCode;
bool isProviderAlreadyLinked(Object error) =>
    errorCodeOf(error) == providerAlreadyLinkedCode;
bool isReferralNotAllowed(Object error) =>
    errorCodeOf(error) == referralNotAllowedCode;
bool isInvalidReferralCode(Object error) =>
    errorCodeOf(error) == invalidReferralCodeCode;
