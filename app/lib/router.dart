import 'package:go_router/go_router.dart';

import 'features/generation_status/generation_status_screen.dart';
import 'features/new_generation/new_generation_screen.dart';

final appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (_, _) => const NewGenerationScreen(),
    ),
    GoRoute(
      path: '/status/:jobId',
      builder: (_, state) => GenerationStatusScreen(
        jobId: state.pathParameters['jobId']!,
      ),
    ),
  ],
);
