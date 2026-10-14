import 'package:go_router/go_router.dart';

import 'features/custom_generation/custom_generation_screen.dart';
import 'features/generation_status/generation_status_screen.dart';
import 'features/home/home_screen.dart';
import 'features/template_detail/template_screen.dart';
import 'schemas/template.dart';

final appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (_, _) => const HomeScreen(),
    ),
    GoRoute(
      path: '/template/:id',
      builder: (_, state) {
        final extra = state.extra;
        return TemplateScreen(
          templateId: state.pathParameters['id']!,
          template: extra is TemplateSummary ? extra : null,
        );
      },
    ),
    GoRoute(
      path: '/create',
      builder: (_, state) => CustomGenerationScreen(
        initialPrompt: state.uri.queryParameters['prompt'] ?? '',
      ),
    ),
    GoRoute(
      path: '/status/:jobId',
      builder: (_, state) => GenerationStatusScreen(
        jobId: state.pathParameters['jobId']!,
      ),
    ),
  ],
);
