import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../features/auth/session_notifier.dart';
import 'generation_service.dart';

final apiClientProvider = Provider<GenerationApiClient>(
  (ref) => DioApiClient(
    tokenProvider: () => ref.read(sessionTokenHolderProvider).token,
    onUnauthorized: () => ref.read(sessionProvider.notifier).expire(),
  ),
);

final generationServiceProvider = Provider<GenerationService>(
  (ref) => GenerationService(ref.watch(apiClientProvider)),
);
