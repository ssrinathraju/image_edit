import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api_client.dart';
import '../../services/generation_service.dart';

final _clientProvider = Provider<GenerationApiClient>((_) => DioApiClient());

final generationServiceProvider = Provider<GenerationService>(
  (ref) => GenerationService(ref.watch(_clientProvider)),
);

class NewGenerationState {
  const NewGenerationState({
    this.faces = const [],
    this.prompt = '',
    this.isSubmitting = false,
  });

  final List<XFile> faces;
  final String prompt;
  final bool isSubmitting;

  bool get canSubmit =>
      faces.isNotEmpty && prompt.trim().isNotEmpty && !isSubmitting;

  NewGenerationState copyWith({
    List<XFile>? faces,
    String? prompt,
    bool? isSubmitting,
  }) {
    return NewGenerationState(
      faces: faces ?? this.faces,
      prompt: prompt ?? this.prompt,
      isSubmitting: isSubmitting ?? this.isSubmitting,
    );
  }
}

class NewGenerationNotifier extends AsyncNotifier<NewGenerationState> {
  @override
  Future<NewGenerationState> build() async => const NewGenerationState();

  void addFace(XFile face) {
    final current = state.valueOrNull ?? const NewGenerationState();
    if (current.faces.length >= 4) return;
    state = AsyncData(current.copyWith(faces: [...current.faces, face]));
  }

  void removeFace(int index) {
    final current = state.valueOrNull ?? const NewGenerationState();
    final updated = List<XFile>.from(current.faces)..removeAt(index);
    state = AsyncData(current.copyWith(faces: updated));
  }

  void setPrompt(String value) {
    final current = state.valueOrNull ?? const NewGenerationState();
    state = AsyncData(current.copyWith(prompt: value));
  }

  Future<String> submit() async {
    final current = state.valueOrNull ?? const NewGenerationState();
    state = AsyncData(current.copyWith(isSubmitting: true));
    try {
      final service = ref.read(generationServiceProvider);
      final jobId = await service.submit(current.faces, current.prompt.trim());
      state = AsyncData(current.copyWith(isSubmitting: false));
      return jobId;
    } catch (_) {
      state = AsyncData(current.copyWith(isSubmitting: false));
      rethrow;
    }
  }

  void reset() {
    state = const AsyncData(NewGenerationState());
  }
}

final newGenerationProvider =
    AsyncNotifierProvider<NewGenerationNotifier, NewGenerationState>(
      NewGenerationNotifier.new,
    );
