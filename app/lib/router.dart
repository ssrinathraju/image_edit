import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/provider_sign_in.dart';
import 'features/auth/confirm_registration_screen.dart';
import 'features/auth/forgot_password_screen.dart';
import 'features/auth/login_screen.dart';
import 'features/auth/referral_prompt_screen.dart';
import 'features/auth/registration_draft.dart';
import 'features/auth/register_screen.dart';
import 'features/auth/reset_password_screen.dart';
import 'features/auth/session_notifier.dart';
import 'features/auth/splash_screen.dart';
import 'features/consent/age_blocked_screen.dart';
import 'features/consent/confirm_age_screen.dart';
import 'features/consent/consent_screen.dart';
import 'features/consent/provider_age_screen.dart';
import 'features/custom_generation/custom_generation_screen.dart';
import 'features/generation_status/generation_status_screen.dart';
import 'features/history/creation_detail_screen.dart';
import 'features/history/creations_screen.dart';
import 'features/home/home_screen.dart';
import 'features/onboarding/onboarding_pages.dart';
import 'features/onboarding/onboarding_store.dart';
import 'features/plans/account_notifier.dart';
import 'features/plans/invite_screen.dart';
import 'features/plans/upgrade_screen.dart';
import 'features/profile/change_email_screen.dart';
import 'features/profile/change_password_screen.dart';
import 'features/profile/confirm_email_change_screen.dart';
import 'features/profile/email_change_draft.dart';
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
const String _providerAge = '/age';
const String _confirmAge = '/confirm-age';
const String _ageBlocked = '/age-blocked';
const String _onboarding = '/onboarding';
const String _howItWorks = '/how-it-works';

/// Pages a signed-out user may open.
const Set<String> _signedOutPages = {
  _login,
  _register,
  _confirmRegistration,
  _forgotPassword,
  _resetPassword,
  _providerAge,
};

/// The only pages open to a signed-in account whose age is not confirmed.
const Set<String> _ageGatePages = {_confirmAge, _ageBlocked};

final routerProvider = Provider<GoRouter>((ref) {
  // Bumped on every session change so go_router re-runs `redirect`.
  final sessionChanges = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => sessionChanges.value++);
  ref.listen(accountProvider, (_, _) => sessionChanges.value++);
  ref.listen(onboardingSeenProvider, (_, _) => sessionChanges.value++);
  ref.onDispose(sessionChanges.dispose);

  String? redirect(Object _, GoRouterState state) {
    final session = ref.read(sessionProvider);
    final location = state.matchedLocation;
    if (session.isLoading || session.hasError) {
      return location == _splash ? null : _splash;
    }
    if (session.value == null) {
      final seen = ref.read(onboardingSeenProvider);
      if (seen.isLoading) return location == _splash ? null : _splash;
      // An unreadable record counts as not seen.
      final hasSeenOnboarding = seen.valueOrNull ?? false;
      if (!hasSeenOnboarding) return location == _onboarding ? null : _onboarding;
      if (location == _onboarding) return _login;
      if (location == _confirmRegistration &&
          ref.read(registrationDraftProvider) == null) {
        return _register;
      }
      if (location == _providerAge && state.extra is! ProviderCredential) {
        return _login;
      }
      return _signedOutPages.contains(location) ? null : _login;
    }
    final account = ref.read(accountProvider);
    if (account.isLoading) return location == _splash ? null : _splash;
    // An account that failed to load is not held back; the server still refuses
    // generation for an unconfirmed age.
    final ageConfirmed = account.valueOrNull?.ageConfirmed ?? true;
    if (!ageConfirmed) return _ageGatePages.contains(location) ? null : _confirmAge;
    if (_ageGatePages.contains(location)) return '/';
    final isAuthPage = _signedOutPages.contains(location) ||
        location == _splash ||
        location == _onboarding;
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
      GoRoute(path: _onboarding, builder: (_, _) => const OnboardingScreen()),
      GoRoute(path: _howItWorks, builder: (_, _) => const HowItWorksScreen()),
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
        path: _providerAge,
        builder: (_, state) =>
            ProviderAgeScreen(credential: state.extra! as ProviderCredential),
      ),
      GoRoute(path: _confirmAge, builder: (_, _) => const ConfirmAgeScreen()),
      GoRoute(path: _ageBlocked, builder: (_, _) => const AgeBlockedScreen()),
      GoRoute(path: '/consent', builder: (_, _) => const ConsentScreen()),
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
      GoRoute(
        path: '/profile/password',
        builder: (_, _) => const ChangePasswordScreen(),
      ),
      GoRoute(
        path: '/profile/email',
        builder: (_, _) => const ChangeEmailScreen(),
      ),
      GoRoute(
        path: '/profile/email/confirm',
        redirect: (_, _) =>
            ref.read(emailChangeDraftProvider) == null ? '/profile/email' : null,
        builder: (_, _) => const ConfirmEmailChangeScreen(),
      ),
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
