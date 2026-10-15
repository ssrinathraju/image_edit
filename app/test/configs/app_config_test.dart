import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/configs/app_config.dart';

void main() {
  test('blank or missing optional values are null', () {
    dotenv.testLoad(fileInput: 'PRIVACY_URL=\nTERMS_URL=   \n');

    expect(AppConfig.privacyUrl, isNull);
    expect(AppConfig.termsUrl, isNull);
    expect(AppConfig.supportEmail, isNull);
  });

  test('set values are returned trimmed', () {
    dotenv.testLoad(
      fileInput: 'PRIVACY_URL= https://example.com/privacy \n'
          'TERMS_URL=https://example.com/terms\n'
          'SUPPORT_EMAIL=help@example.com\n',
    );

    expect(AppConfig.privacyUrl, 'https://example.com/privacy');
    expect(AppConfig.termsUrl, 'https://example.com/terms');
    expect(AppConfig.supportEmail, 'help@example.com');
  });
}
