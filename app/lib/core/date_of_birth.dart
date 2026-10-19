/// A date as `YYYY-MM-DD`, the form the server takes for a date of birth.
String formatIsoDate(DateTime date) {
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  return '${date.year.toString().padLeft(4, '0')}-$month-$day';
}

/// Where the date picker opens: someone exactly 18 today.
DateTime eighteenYearsBefore(DateTime today) =>
    DateTime(today.year - 18, today.month, today.day);
