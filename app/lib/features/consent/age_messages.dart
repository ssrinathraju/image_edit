import '../../core/api_errors.dart';
import '../common/error_message.dart';

const String underAgeMessage = 'You must be 18 or older to use this app';
const String invalidDateOfBirthMessage = 'Enter a valid date of birth';

/// The message for a refused date of birth, or [describeError] for anything else.
String describeDateOfBirthError(Object error) {
  if (isUnderAge(error)) return underAgeMessage;
  if (isInvalidDateOfBirth(error)) return invalidDateOfBirthMessage;
  return describeError(error);
}
