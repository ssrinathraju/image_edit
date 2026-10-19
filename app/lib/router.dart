import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'features/auth/confirm_registration_screen.dart';
import 'features/auth/forgot_password_screen.dart';
import 'features/auth/login_screen.dart';
import 'features/auth/referral_prompt_screen.dart';
import 'features/auth/registration_draft.dart';
import 'features/auth/register_screen.dart';
import 'features/auth/reset_password_screen.dart';
import 'features/auth/session_notifier.dart';
import 'features/auth/splash_screen.dart';
import 'features/custom_generation/custom_generation_screen.dart';
import 'features/generation_status/generation_status_screen.dart';
import 'features/history/creation_detail_screen.dart';
import 'features/history/creations_screen.dart';
import 'features/home/home_screen.dart';
import 'features/plans/invite_screen.dart';
import 'features/plans/upgrade_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/template_detail/template_screen.dart';
import 'schemas/template.dart';

const String _splash = '/splash';
const String _login = '/login';
const String _register = '/register';
const String _forgotPassword = '/forgot-password';
const String _resetPassword = '/reset-password';
const String _confirmRegistration = '/confirm-registration';
const String _referralPrompt = '/referral-prompt';

/// Pages a signed-out user may open.
const Set<String> _signedOutPages = {
  _login,
  _register,
  _confirmRegistration,
  _forgotPassword,
  _resetPassword,
};

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
      if (location == _confirmRegistration &&
          ref.read(registrationDraftProvider) == null) {
        return _register;
      }
      return _signedOutPages.contains(location) ? null : _login;
    }
    final isAuthPage = _signedOutPages.contains(location) || location == _splash;
    if (!isAuthPage) return null;
    final notifier = ref.read(sessionProvider.notifier);
    if (notifier.justCreatedViaProvider) return _referralPrompt;
    return '/';
  }

  final router = GoRouter(
    refreshListenable: sessionChanges,
    redirect: redirect,
    initialLocation: _splash,
    routes: [
      GoRoute(path: _splash, builder: (_, _) => const SplashScreen()),
      GoRoute(path: _login, builder: (_, _) => const LoginScreen()),
      GoRoute(path: _register, builder: (_, _) => const RegisterScreen()),
      GoRoute(
        path: _forgotPassword,
        builder: (_, state) => ForgotPasswordScreen(
          initialEmail: state.uri.queryParameters['email'] ?? '',
        ),
      ),
      GoRoute(
        path: _resetPassword,
        builder: (_, state) => ResetPasswordScreen(
          email: state.uri.queryParameters['email'] ?? '',
        ),
      ),
      GoRoute(
        path: _confirmRegistration,
        builder: (_, _) => const ConfirmRegistrationScreen(),
      ),
      GoRoute(
        path: _referralPrompt,
        builder: (_, _) => const ReferralPromptScreen(),
      ),
      GoRoute(path: '/', builder: (_, _) => const HomeScreen()),
      GoRoute(path: '/creations', builder: (_, _) => const CreationsScreen()),
      GoRoute(
        path: '/creations/:jobId',
        builder: (_, state) =>
            CreationDetailScreen(jobId: state.pathParameters['jobId']!),
      ),
      GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen()),
      GoRoute(path: '/upgrade', builder: (_, _) => const UpgradeScreen()),
      GoRoute(path: '/invite', builder: (_, _) => const InviteScreen()),
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
