import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const String _xmlDir = 'android/app/src/main/res/xml';

/// Returns the text of the named section (the whole file when [tag] is null).
String _section(String file, String? tag) {
  final text = File('$_xmlDir/$file').readAsStringSync();
  if (tag == null) return text;
  final match = RegExp('<$tag>(.*?)</$tag>', dotAll: true).firstMatch(text);
  expect(match, isNotNull, reason: '$file has no <$tag>');
  return match!.group(1)!;
}

void _expectExcluded(String section) {
  for (final path in ['creations/', 'onboarding_seen']) {
    expect(section, contains('<exclude domain="file" path="$path" />'));
  }
}

void main() {
  test('backup_rules.xml keeps the creations and the seen marker out', () {
    _expectExcluded(_section('backup_rules.xml', null));
  });

  for (final tag in ['cloud-backup', 'device-transfer']) {
    test('data_extraction_rules.xml excludes both from $tag', () {
      _expectExcluded(_section('data_extraction_rules.xml', tag));
    });
  }
}
