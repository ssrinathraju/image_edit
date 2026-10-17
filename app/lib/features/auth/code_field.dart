import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../configs/app_config.dart';

/// A field for the emailed code: digits only, capped at the code length.
class CodeField extends StatelessWidget {
  const CodeField({required this.controller, required this.onChanged, super.key});

  final TextEditingController controller;
  final VoidCallback onChanged;

  static bool isComplete(String value) =>
      value.length == AppConfig.emailCodeLength;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      autocorrect: false,
      inputFormatters: [
        FilteringTextInputFormatter.digitsOnly,
        LengthLimitingTextInputFormatter(AppConfig.emailCodeLength),
      ],
      decoration: const InputDecoration(
        labelText: 'Code',
        border: OutlineInputBorder(),
      ),
      onChanged: (_) => onChanged(),
    );
  }
}
