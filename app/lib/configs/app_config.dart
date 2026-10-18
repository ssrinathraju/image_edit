import 'package:flutter/foundation.dart';
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

  static String? get googleIosClientId => _optional('GOOGLE_IOS_CLIENT_ID');
  static String? get googleServerClientId => _optional('GOOGLE_SERVER_CLIENT_ID');

  /// True only for an explicit `APPLE_SIGN_IN=true`.
  static bool get isAppleSignInEnabled =>
      _optional('APPLE_SIGN_IN')?.toLowerCase() == 'true';

  /// Google needs the server client ID everywhere, and the iOS client ID on iOS.
  static bool isGoogleSignInAvailable(TargetPlatform platform) {
    if (googleServerClientId == null) return false;
    return switch (platform) {
      TargetPlatform.iOS => googleIosClientId != null,
      TargetPlatform.android => true,
      _ => false,
    };
  }

  static bool isAppleSignInAvailable(TargetPlatform platform) =>
      platform == TargetPlatform.iOS && isAppleSignInEnabled;

  static String? _optional(String key) {
    // Widget tests build screens without loading a .env; treat that as nothing configured.
    final value = dotenv.isInitialized ? dotenv.env[key]?.trim() : null;
    return value == null || value.isEmpty ? null : value;
  }
}
