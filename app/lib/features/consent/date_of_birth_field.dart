import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/date_of_birth.dart';
import '../common/clock.dart';

final DateTime _earliestBirthDate = DateTime(1900);

/// Opens the date picker; tests replace it to choose a date without tapping the calendar.
typedef DateOfBirthPicker = Future<DateTime?> Function(
  BuildContext context, {
  required DateTime initialDate,
  required DateTime lastDate,
});

final dateOfBirthPickerProvider = Provider<DateOfBirthPicker>(
  (_) => (context, {required initialDate, required lastDate}) => showDatePicker(
        context: context,
        initialDate: initialDate,
        firstDate: _earliestBirthDate,
        lastDate: lastDate,
        helpText: 'Date of birth',
      ),
);

/// A tappable "Date of birth" field that shows the chosen date as `YYYY-MM-DD`.
class DateOfBirthField extends ConsumerWidget {
  const DateOfBirthField({
    required this.value,
    required this.onChanged,
    this.enabled = true,
    super.key,
  });

  final DateTime? value;
  final ValueChanged<DateTime> onChanged;
  final bool enabled;

  Future<void> _pick(BuildContext context, WidgetRef ref) async {
    final today = ref.read(clockProvider)();
    final picked = await ref.read(dateOfBirthPickerProvider)(
      context,
      initialDate: value ?? eighteenYearsBefore(today),
      lastDate: DateTime(today.year, today.month, today.day),
    );
    if (picked != null) onChanged(picked);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chosen = value;
    return InkWell(
      onTap: enabled ? () => _pick(context, ref) : null,
      child: InputDecorator(
        decoration: const InputDecoration(
          labelText: 'Date of birth',
          border: OutlineInputBorder(),
          suffixIcon: Icon(Icons.calendar_today_outlined),
        ),
        child: Text(chosen == null ? 'Choose a date' : formatIsoDate(chosen)),
      ),
    );
  }
}
