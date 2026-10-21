import 'dart:io';

import 'package:image_edit/features/onboarding/onboarding_store.dart';

class InMemoryOnboardingStore implements OnboardingStore {
  InMemoryOnboardingStore({this.seen = true, this.failSave = false});

  bool seen;
  final bool failSave;
  int saveCalls = 0;

  @override
  Future<Directory> Function() get resolveRoot =>
      throw UnsupportedError('in-memory store has no folder');

  @override
  Future<bool> hasSeen() async => seen;

  @override
  Future<void> markSeen() async {
    saveCalls++;
    if (!failSave) seen = true;
  }
}
