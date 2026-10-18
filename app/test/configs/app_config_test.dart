import 'package:flutter/foundation.dart';
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

  test('the invite url is optional', () {
    dotenv.testLoad(fileInput: 'INVITE_URL=\n');
    expect(AppConfig.inviteUrl, isNull);

    dotenv.testLoad(fileInput: 'INVITE_URL=https://example.com/get\n');
    expect(AppConfig.inviteUrl, 'https://example.com/get');
  });

  group('provider sign-in configuration', () {
    test('blank or missing values read as not configured', () {
      dotenv.testLoad(fileInput: 'GOOGLE_IOS_CLIENT_ID=\nAPPLE_SIGN_IN=  \n');

      expect(AppConfig.googleIosClientId, isNull);
      expect(AppConfig.googleServerClientId, isNull);
      expect(AppConfig.isAppleSignInEnabled, isFalse);
    });

    test('set values are returned trimmed', () {
      dotenv.testLoad(
        fileInput: 'GOOGLE_IOS_CLIENT_ID= ios.apps \n'
            'GOOGLE_SERVER_CLIENT_ID=web.apps\nAPPLE_SIGN_IN=true\n',
      );

      expect(AppConfig.googleIosClientId, 'ios.apps');
      expect(AppConfig.googleServerClientId, 'web.apps');
      expect(AppConfig.isAppleSignInEnabled, isTrue);
    });

    test('only an explicit true enables Apple', () {
      dotenv.testLoad(fileInput: 'APPLE_SIGN_IN=yes\n');
      expect(AppConfig.isAppleSignInEnabled, isFalse);

      dotenv.testLoad(fileInput: 'APPLE_SIGN_IN=TRUE\n');
      expect(AppConfig.isAppleSignInEnabled, isTrue);
    });

    test('Google needs the server client ID, plus the iOS one on iOS', () {
      dotenv.testLoad(fileInput: 'GOOGLE_SERVER_CLIENT_ID=web.apps\n');
      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.android), isTrue);
      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.iOS), isFalse);

      dotenv.testLoad(
        fileInput: 'GOOGLE_SERVER_CLIENT_ID=web.apps\nGOOGLE_IOS_CLIENT_ID=ios.apps\n',
      );
      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.iOS), isTrue);

      dotenv.testLoad(fileInput: 'GOOGLE_IOS_CLIENT_ID=ios.apps\n');
      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.iOS), isFalse);
      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.android), isFalse);
    });

    test('Google is offered only on iOS and Android', () {
      dotenv.testLoad(
        fileInput: 'GOOGLE_SERVER_CLIENT_ID=web.apps\nGOOGLE_IOS_CLIENT_ID=ios.apps\n',
      );

      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.macOS), isFalse);
      expect(AppConfig.isGoogleSignInAvailable(TargetPlatform.windows), isFalse);
    });

    test('Apple is offered only on iOS when enabled', () {
      dotenv.testLoad(fileInput: 'APPLE_SIGN_IN=true\n');
      expect(AppConfig.isAppleSignInAvailable(TargetPlatform.iOS), isTrue);
      expect(AppConfig.isAppleSignInAvailable(TargetPlatform.android), isFalse);

      dotenv.testLoad(fileInput: 'APPLE_SIGN_IN=\n');
      expect(AppConfig.isAppleSignInAvailable(TargetPlatform.iOS), isFalse);
    });
  });
}
