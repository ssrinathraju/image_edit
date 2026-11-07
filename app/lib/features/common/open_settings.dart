import 'package:flutter/material.dart';

import '../../services/app_settings.dart';

/// Opens the app's page in the device settings, or says it could not.
Future<void> openSettingsOrExplain(
  ScaffoldMessengerState messenger,
  AppSettings settings,
) async {
  if (await settings.open()) return;
  messenger.showSnackBar(
    const SnackBar(content: Text('Could not open Settings.')),
  );
}
