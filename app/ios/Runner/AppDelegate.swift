import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    registerBackupChannel(with: engineBridge.pluginRegistry)
    registerSettingsChannel(with: engineBridge.pluginRegistry)
  }

  private func registerSettingsChannel(with registry: FlutterPluginRegistry) {
    guard let registrar = registry.registrar(forPlugin: "AppSettings") else { return }
    let channel = FlutterMethodChannel(
      name: "image_edit/settings",
      binaryMessenger: registrar.messenger()
    )
    channel.setMethodCallHandler { call, result in
      guard call.method == "open",
        let url = URL(string: UIApplication.openSettingsURLString)
      else {
        result(FlutterMethodNotImplemented)
        return
      }
      UIApplication.shared.open(url) { opened in
        if opened {
          result(nil)
        } else {
          result(FlutterError(code: "open_failed", message: "Settings did not open", details: nil))
        }
      }
    }
  }

  private func registerBackupChannel(with registry: FlutterPluginRegistry) {
    guard let registrar = registry.registrar(forPlugin: "BackupExclusion") else { return }
    let channel = FlutterMethodChannel(
      name: "image_edit/backup",
      binaryMessenger: registrar.messenger()
    )
    channel.setMethodCallHandler { call, result in
      guard call.method == "excludeFromBackup", let path = call.arguments as? String else {
        result(FlutterMethodNotImplemented)
        return
      }
      do {
        var url = URL(fileURLWithPath: path)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try url.setResourceValues(values)
        result(nil)
      } catch {
        result(FlutterError(code: "exclude_failed", message: error.localizedDescription, details: nil))
      }
    }
  }
}
