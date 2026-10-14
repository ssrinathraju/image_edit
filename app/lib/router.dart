import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'features/auth/login_screen.dart';
import 'features/auth/register_screen.dart';
import 'features/auth/session_notifier.dart';
import 'features/auth/splash_screen.dart';
import 'features/custom_generation/custom_generation_screen.dart';
import 'features/generation_status/generation_status_screen.dart';
import 'features/home/home_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/template_detail/template_screen.dart';
import 'schemas/template.dart';

const String _splash = '/splash';
const String _login = '/login';
const String _register = '/register';

final routerProvider = Provider<GoRouter>((ref) {
  // Bumped on every session change so go_router re-runs `redirect`.
  final sessionChanges = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => sessionChanges.value++);
  ref.onDispose(sessionChanges.dispose);

  String? redirect(Object _, GoRouterState state) {
    final session = ref.read(sessionProvider);
    final location = state.matchedLocation;
    if (session.isLoading || session.hasError) {
      return location == _splash ? null : _splash;
    }
    if (session.value == null) {
      return location == _login || location == _register ? null : _login;
    }
    final isAuthPage =
        location == _login || location == _register || location == _splash;
    return isAuthPage ? '/' : null;
  }

  final router = GoRouter(
    refreshListenable: sessionChanges,
    redirect: redirect,
    initialLocation: _splash,
    routes: [
      GoRoute(path: _splash, builder: (_, _) => const SplashScreen()),
      GoRoute(path: _login, builder: (_, _) => const LoginScreen()),
      GoRoute(path: _register, builder: (_, _) => const RegisterScreen()),
      GoRoute(path: '/', builder: (_, _) => const HomeScreen()),
      GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen()),
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
  ref.onDispose(router.dispose);
  return router;
});
