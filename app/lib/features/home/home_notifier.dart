import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../schemas/template.dart';
import '../../services/generation_providers.dart';

const Duration searchDebounce = Duration(milliseconds: 300);

final homeDebounceProvider = Provider<Duration>((_) => searchDebounce);

class HomeNotifier extends AutoDisposeAsyncNotifier<List<TemplateSummary>> {
  Timer? _debounce;
  int _sequence = 0;
  String _query = '';
  bool _disposed = false;

  @override
  Future<List<TemplateSummary>> build() {
    ref.onDispose(() {
      _disposed = true;
      _debounce?.cancel();
    });
    return _fetch();
  }

  /// Updates the search text and reloads once typing pauses.
  void setQuery(String query) {
    _query = query;
    _debounce?.cancel();
    _debounce = Timer(ref.read(homeDebounceProvider), _reload);
  }

  Future<void> retry() {
    _debounce?.cancel();
    state = const AsyncLoading();
    return _reload();
  }

  Future<void> _reload() async {
    final sequence = ++_sequence;
    final result = await AsyncValue.guard(_fetch);
    if (sequence != _sequence || _disposed) return;
    state = result;
  }

  Future<List<TemplateSummary>> _fetch() {
    final query = _query.trim();
    return ref
        .read(generationServiceProvider)
        .listTemplates(query: query.isEmpty ? null : query);
  }
}

final homeNotifierProvider =
    AsyncNotifierProvider.autoDispose<HomeNotifier, List<TemplateSummary>>(
  HomeNotifier.new,
);
