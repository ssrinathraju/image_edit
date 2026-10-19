import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/date_of_birth.dart';

void main() {
  test('a date is written as zero-padded YYYY-MM-DD', () {
    expect(formatIsoDate(DateTime(2001, 3, 4)), '2001-03-04');
    expect(formatIsoDate(DateTime(1990, 12, 31)), '1990-12-31');
    expect(formatIsoDate(DateTime(987, 1, 2)), '0987-01-02');
  });

  test('the picker opens on the date exactly 18 years before today', () {
    expect(eighteenYearsBefore(DateTime(2026, 10, 20)), DateTime(2008, 10, 20));
  });
}
