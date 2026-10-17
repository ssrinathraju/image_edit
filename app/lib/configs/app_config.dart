import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static const int maxPromptChars = 500;
  static const int minPasswordChars = 8;
  static const int emailCodeLength = 6;
  static const int resendCooldownSeconds = 60;

  static String get apiBaseUrl =>
      dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

  /// Optional entries: a blank or missing value hides the matching profile row.
  static String? get privacyUrl => _optional('PRIVACY_URL');
  static String? get termsUrl => _optional('TERMS_URL');
  static String? get supportEmail => _optional('SUPPORT_EMAIL');
  static String? get inviteUrl => _optional('INVITE_URL');

  static String? _optional(String key) {
    final value = dotenv.env[key]?.trim();
    return value == null || value.isEmpty ? null : value;
  }
}
