/// The words the consent screen shows for one version.
class ConsentText {
  const ConsentText({required this.intro, required this.points});

  final String intro;
  final List<String> points;
}

// Placeholder wording: it must be reviewed for GDPR and BIPA before launch
// (see todo.md), and CONSENT_VERSION on the server bumped when it changes.
const Map<String, ConsentText> _consentTexts = {
  '1': ConsentText(
    intro: 'Before we use your photo, please read how photos and results are handled.',
    points: [
      'Your photo is used for this generation only and is deleted after the job.',
      'The result is kept on our server for 24 hours.',
      'Your creations are stored on this device.',
      'Only upload photos of yourself or of people who agreed.',
    ],
  ),
};

/// The text for [version], or null when this app has none: consent is only ever
/// recorded for a version whose words the user was shown.
ConsentText? consentTextFor(String version) => _consentTexts[version];
