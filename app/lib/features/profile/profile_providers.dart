import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../configs/app_config.dart';

/// Opens a link outside the app; returns false when nothing could handle it.
abstract class LinkLauncher {
  Future<bool> open(Uri uri);
}

class PlatformLinkLauncher implements LinkLauncher {
  const PlatformLinkLauncher();

  @override
  Future<bool> open(Uri uri) =>
      launchUrl(uri, mode: LaunchMode.externalApplication);
}

final linkLauncherProvider =
    Provider<LinkLauncher>((_) => const PlatformLinkLauncher());

class ProfileLinks {
  const ProfileLinks({this.privacyUrl, this.termsUrl, this.supportEmail});

  final String? privacyUrl;
  final String? termsUrl;
  final String? supportEmail;
}

final profileLinksProvider = Provider<ProfileLinks>(
  (_) => ProfileLinks(
    privacyUrl: AppConfig.privacyUrl,
    termsUrl: AppConfig.termsUrl,
    supportEmail: AppConfig.supportEmail,
  ),
);

/// Shown as `version (build)`.
final appVersionProvider = FutureProvider<String>((_) async {
  final info = await PackageInfo.fromPlatform();
  return '${info.version} (${info.buildNumber})';
});
