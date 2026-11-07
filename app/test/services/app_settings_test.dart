import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/services/app_settings.dart';
import 'package:logging/logging.dart';

const MethodChannel _channel = MethodChannel('image_edit/settings');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_channel, null);
  });

  test(
    'open invokes "open" on the settings channel and reports success',
    () async {
      final calls = <String>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(_channel, (call) async {
            calls.add(call.method);
            return null;
          });

      expect(await const PlatformAppSettings().open(), isTrue);
      expect(calls, ['open']);
    },
  );

  test('a channel error is logged by type and reported as failure', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_channel, (call) async {
          throw PlatformException(
            code: 'open_failed',
            message: 'secret detail',
          );
        });
    final records = <LogRecord>[];
    final sub = Logger('AppSettings').onRecord.listen(records.add);
    addTearDown(sub.cancel);

    expect(await const PlatformAppSettings().open(), isFalse);
    expect(records.single.level, Level.WARNING);
    expect(records.single.message, 'open_failed PlatformException');
  });

  test('a missing handler is also reported as failure', () async {
    expect(await const PlatformAppSettings().open(), isFalse);
  });
}
