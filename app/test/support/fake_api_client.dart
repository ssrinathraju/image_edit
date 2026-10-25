import 'dart:typed_data';

import 'package:image_edit/core/api_client.dart';
import 'package:image_edit/core/reauth.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/schemas/account.dart';
import 'package:image_edit/schemas/session.dart';
import 'package:image_edit/schemas/template.dart';

class FakeApiClient implements GenerationApiClient {
  Future<List<TemplateSummary>> Function(String? query) onListTemplates = (
    _,
  ) async => const [];
  Future<String> Function(GenerationRequest request) onSubmit = (_) async =>
      'job-1';
  Future<GenerationJob> Function(String jobId) onStatus = (id) async =>
      GenerationJob(jobId: id, status: JobStatus.queued);
  Future<Uint8List> Function(String url) onFetchBytes = (_) async =>
      Uint8List.fromList([1, 2, 3]);

  Future<void> Function(String email, String password) onRegister = (
    _,
    _,
  ) async {};
  Future<Session> Function(String email, String code) onConfirmRegistration = (
    email,
    _,
  ) async => Session(token: 'token-new', userId: 'user-1', email: email);
  final referralCodes = <String?>[];
  final registrationPasswords = <String>[];
  final confirmedRegistrations = <List<String>>[];
  Future<Session> Function(String email, String password) onLogin = (
    email,
    _,
  ) async => Session(token: 'token-1', userId: 'user-1', email: email);
  Future<void> Function() onLogout = () async {};
  Future<UserProfile> Function() onFetchMe = () async =>
      const UserProfile(id: 'user-1', email: 'ana@example.com');
  Future<void> Function(String password) onDeleteAccount = (_) async {};
  Future<void> Function(String provider, String token, String? nonce)
  onDeleteWithProvider = (_, _, _) async {};
  Future<ProviderSession> Function(String idToken) onSignInWithGoogle =
      (_) async => const ProviderSession(
        session: Session(
          token: 'token-google',
          userId: 'user-2',
          email: 'gina@example.com',
        ),
        created: false,
      );
  Future<ProviderSession> Function(
    String identityToken,
    String nonce,
    String authorizationCode,
  )
  onSignInWithApple = (_, _, _) async => const ProviderSession(
    session: Session(
      token: 'token-apple',
      userId: 'user-3',
      email: 'ann@example.com',
    ),
    created: false,
  );
  Future<void> Function(String code) onRedeemReferral = (_) async {};
  Future<void> Function() onSubmitReport = () async {};
  final submittedReports =
      <({String jobId, String category, String note, Uint8List imageBytes})>[];
  Future<void> Function(String email) onRequestPasswordReset = (_) async {};
  Future<Session> Function(String email, String code, String newPassword)
  onConfirmPasswordReset = (email, _, _) async =>
      Session(token: 'token-reset', userId: 'user-1', email: email);

  Future<void> Function(String newPassword, Reauth reauth) onChangePassword = (
    _,
    _,
  ) async {};
  Future<void> Function(String newEmail, Reauth reauth) onRequestEmailChange = (
    _,
    _,
  ) async {};
  Future<String> Function(String code) onConfirmEmailChange = (_) async =>
      'new@example.com';
  Future<void> Function(String idToken) onLinkGoogle = (_) async {};
  Future<void> Function(String identityToken, String nonce, String code)
  onLinkApple = (_, _, _) async {};
  Future<void> Function(String provider, Reauth reauth) onUnlinkProvider = (
    _,
    _,
  ) async {};

  final changedPasswords = <({String newPassword, Reauth reauth})>[];
  final emailChangeRequests = <({String newEmail, Reauth reauth})>[];
  final confirmedEmailCodes = <String>[];
  final linkedGoogleTokens = <String>[];
  final linkReauths = <Reauth>[];
  final linkedApple = <List<String>>[];
  final unlinked = <({String provider, Reauth reauth})>[];

  Future<void> Function(DateTime dateOfBirth) onConfirmAge = (_) async {};
  Future<void> Function(String version) onAcceptConsent = (_) async {};
  Future<void> Function() onWithdrawConsent = () async {};

  final registeredDates = <DateTime>[];
  final googleDates = <DateTime?>[];
  final appleDates = <DateTime?>[];
  final confirmedAges = <DateTime>[];
  final acceptedConsents = <String>[];
  var withdrawnConsents = 0;

  final queries = <String?>[];
  final registered = <String>[];
  final loggedIn = <String>[];
  var logoutCalls = 0;
  final deletedWith = <String>[];
  final deletedViaProvider = <List<String?>>[];
  final googleTokens = <String>[];
  final appleSignIns = <List<String>>[];
  final redeemedCodes = <String>[];
  final resetRequestedFor = <String>[];
  final resetConfirmed = <List<String>>[];
  final submitted = <GenerationRequest>[];
  final statusCalls = <String>[];

  @override
  Future<List<TemplateSummary>> listTemplates({String? query}) {
    queries.add(query);
    return onListTemplates(query);
  }

  @override
  Future<String> submitGeneration(GenerationRequest request) {
    submitted.add(request);
    return onSubmit(request);
  }

  @override
  Future<GenerationJob> getJobStatus(String jobId) {
    statusCalls.add(jobId);
    return onStatus(jobId);
  }

  @override
  Future<Uint8List> fetchImageBytes(String url) => onFetchBytes(url);

  @override
  String resolveUrl(String path) => 'http://fake$path';

  @override
  Future<void> register({
    required String email,
    required String password,
    required DateTime dateOfBirth,
    String? referralCode,
  }) {
    registered.add(email);
    registeredDates.add(dateOfBirth);
    registrationPasswords.add(password);
    referralCodes.add(referralCode);
    return onRegister(email, password);
  }

  @override
  Future<Session> confirmRegistration({
    required String email,
    required String code,
    required String password,
  }) {
    confirmedRegistrations.add([email, code, password]);
    return onConfirmRegistration(email, code);
  }

  @override
  Future<Session> login({required String email, required String password}) {
    loggedIn.add(email);
    return onLogin(email, password);
  }

  @override
  Future<void> logout() {
    logoutCalls++;
    return onLogout();
  }

  @override
  Future<UserProfile> fetchMe() => onFetchMe();

  @override
  Future<void> deleteAccount({
    String? password,
    String? provider,
    String? token,
    String? nonce,
  }) {
    if (provider != null) {
      deletedViaProvider.add([provider, token, nonce]);
      return onDeleteWithProvider(provider, token!, nonce);
    }
    deletedWith.add(password!);
    return onDeleteAccount(password);
  }

  @override
  Future<ProviderSession> signInWithGoogle({
    required String idToken,
    DateTime? dateOfBirth,
  }) {
    googleTokens.add(idToken);
    googleDates.add(dateOfBirth);
    return onSignInWithGoogle(idToken);
  }

  @override
  Future<ProviderSession> signInWithApple({
    required String identityToken,
    required String nonce,
    required String authorizationCode,
    DateTime? dateOfBirth,
  }) {
    appleSignIns.add([identityToken, nonce, authorizationCode]);
    appleDates.add(dateOfBirth);
    return onSignInWithApple(identityToken, nonce, authorizationCode);
  }

  @override
  Future<void> confirmAge({required DateTime dateOfBirth}) {
    confirmedAges.add(dateOfBirth);
    return onConfirmAge(dateOfBirth);
  }

  @override
  Future<void> acceptConsent({required String version}) {
    acceptedConsents.add(version);
    return onAcceptConsent(version);
  }

  @override
  Future<void> withdrawConsent() {
    withdrawnConsents++;
    return onWithdrawConsent();
  }

  @override
  Future<void> redeemReferral({required String code}) {
    redeemedCodes.add(code);
    return onRedeemReferral(code);
  }

  @override
  Future<void> submitReport({
    required String jobId,
    required String category,
    required String note,
    required Uint8List imageBytes,
  }) {
    submittedReports.add((
      jobId: jobId,
      category: category,
      note: note,
      imageBytes: imageBytes,
    ));
    return onSubmitReport();
  }

  @override
  Future<void> changePassword({
    required String newPassword,
    required Reauth reauth,
  }) {
    changedPasswords.add((newPassword: newPassword, reauth: reauth));
    return onChangePassword(newPassword, reauth);
  }

  @override
  Future<void> requestEmailChange({
    required String newEmail,
    required Reauth reauth,
  }) {
    emailChangeRequests.add((newEmail: newEmail, reauth: reauth));
    return onRequestEmailChange(newEmail, reauth);
  }

  @override
  Future<String> confirmEmailChange({required String code}) {
    confirmedEmailCodes.add(code);
    return onConfirmEmailChange(code);
  }

  @override
  Future<void> linkGoogle({required String idToken, required Reauth reauth}) {
    linkedGoogleTokens.add(idToken);
    linkReauths.add(reauth);
    return onLinkGoogle(idToken);
  }

  @override
  Future<void> linkApple({
    required String identityToken,
    required String nonce,
    required String authorizationCode,
    required Reauth reauth,
  }) {
    linkReauths.add(reauth);
    linkedApple.add([identityToken, nonce, authorizationCode]);
    return onLinkApple(identityToken, nonce, authorizationCode);
  }

  @override
  Future<void> unlinkProvider({
    required String provider,
    required Reauth reauth,
  }) {
    unlinked.add((provider: provider, reauth: reauth));
    return onUnlinkProvider(provider, reauth);
  }

  @override
  Future<void> requestPasswordReset({required String email}) {
    resetRequestedFor.add(email);
    return onRequestPasswordReset(email);
  }

  @override
  Future<Session> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) {
    resetConfirmed.add([email, code, newPassword]);
    return onConfirmPasswordReset(email, code, newPassword);
  }
}

TemplateSummary fakeTemplate(
  String id, {
  String? title,
  List<String> tags = const [],
}) => TemplateSummary(
  id: id,
  title: title ?? id,
  tags: tags,
  previewUrl: 'http://fake/template-previews/$id.webp',
);

/// A `/me` payload with usage and referral details, as the new server sends.
UserProfile fakeProfile({
  String email = 'ana@example.com',
  Plan plan = Plan.free,
  int dailyLimit = 3,
  int usedToday = 0,
  int bonusCredits = 0,
  int rewards = 0,
  String code = 'K7M2QX9P',
  DateTime? resetsAt,
  List<String> providers = const [],
  bool hasPassword = true,
  bool ageConfirmed = true,
  bool consentGiven = true,
  String acceptedConsentVersion = '1',
  String currentConsentVersion = '1',
}) => UserProfile(
  id: 'user-1',
  email: email,
  providers: providers,
  hasPassword: hasPassword,
  ageConfirmed: ageConfirmed,
  consent: ConsentState(
    currentVersion: currentConsentVersion,
    acceptedVersion: consentGiven ? acceptedConsentVersion : null,
    acceptedAt: consentGiven ? DateTime.utc(2026, 10, 19, 12) : null,
  ),
  plan: plan,
  usage: Usage(
    dailyLimit: dailyLimit,
    usedToday: usedToday,
    bonusCredits: bonusCredits,
    remaining: (dailyLimit - usedToday).clamp(0, dailyLimit) + bonusCredits,
    resetsAt: resetsAt ?? DateTime.utc(2026, 10, 17),
    planLimits: const {'free': 3, 'premium': 30},
  ),
  referral: Referral(
    code: code,
    rewards: rewards,
    maxRewards: 10,
    bonusPerReferral: 5,
  ),
);
