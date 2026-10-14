import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static const int maxPromptChars = 500;

  static String get apiBaseUrl =>
      dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';
}
