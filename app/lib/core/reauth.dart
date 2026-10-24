import 'provider_sign_in.dart';

/// Proof that the caller owns the account: its current password, or a fresh
/// sign-in with a linked provider for an account that has no password.
class Reauth {
  const Reauth.password(String this.password) : credential = null;
  const Reauth.provider(ProviderCredential this.credential) : password = null;

  final String? password;
  final ProviderCredential? credential;

  /// The provider that confirmed, or null when a password did.
  SignInProvider? get provider => credential?.provider;

  Map<String, Object> toJson() {
    final credential = this.credential;
    if (credential == null) return {'password': password!};
    return {
      'provider': credential.provider.apiName,
      'token': credential.token,
      'nonce': ?credential.nonce,
    };
  }
}
