import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The current time; tests replace it with a fixed one.
final clockProvider = Provider<DateTime Function()>((_) => DateTime.now);
