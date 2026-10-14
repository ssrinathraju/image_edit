import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import 'generation_service.dart';

final apiClientProvider = Provider<GenerationApiClient>((_) => DioApiClient());

final generationServiceProvider = Provider<GenerationService>(
  (ref) => GenerationService(ref.watch(apiClientProvider)),
);
