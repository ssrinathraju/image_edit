import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/generation_providers.dart';
import 'generation_request.dart';

final lastRequestProvider = StateProvider<GenerationRequest?>((_) => null);

class SubmitController extends Notifier<bool> {
  @override
  bool build() => false;

  /// Submits the request and returns the new job id; state is `isSubmitting`.
  Future<String> submit(GenerationRequest request) async {
    state = true;
    try {
      final jobId = await ref.read(generationServiceProvider).submit(request);
      ref.read(lastRequestProvider.notifier).state = request;
      return jobId;
    } finally {
      state = false;
    }
  }
}

final submitControllerProvider =
    NotifierProvider<SubmitController, bool>(SubmitController.new);
