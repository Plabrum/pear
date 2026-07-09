import Foundation

// Plain NSObject — see PearNotificationsModule.swift's header comment for why this
// doesn't conform to RCTBridgeModule directly (that's added via an Objective-C
// category in the companion .m file).
@objc(PearUpdatesModule)
class PearUpdatesModule: NSObject {
  @objc static func requiresMainQueueSetup() -> Bool { false }

  // Called from RootNavigator's <NavigationContainer onReady={...}> — "user
  // reached an interactive screen," a more meaningful signal than the old
  // splash-hide effect that markBootSuccessful replaces.
  @objc func markBootSuccessful() {
    UpdatesManager.shared.markBootSuccessful()
  }

  @objc func getCurrentUpdateInfo(
    _ resolve: @escaping (Any?) -> Void,
    reject: @escaping (String, String, Error?) -> Void
  ) {
    resolve(UpdatesManager.shared.getCurrentUpdateInfo())
  }
}
