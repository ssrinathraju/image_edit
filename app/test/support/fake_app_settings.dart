import 'package:image_edit/services/app_settings.dart';

class FakeAppSettings implements AppSettings {
  FakeAppSettings({this.opens = true});

  final bool opens;
  int openCount = 0;

  @override
  Future<bool> open() async {
    openCount++;
    return opens;
  }
}
