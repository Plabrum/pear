import Foundation
import UIKit
import UserNotifications

// Plain NSObject, not `RCTBridgeModule`-conforming in Swift — the companion
// PearNotificationsModule.m's RCT_EXTERN_MODULE macro adds that conformance via
// an Objective-C category, React Native's documented pattern for Swift-implemented
// bridge modules. Promise resolve/reject params are typed as plain closures
// (not the RCTPromiseResolveBlock/RCTPromiseRejectBlock typealiases) so this file
// never needs to import React/RCTBridgeModule.h — their block signatures are
// structurally identical, so the .m's RCT_EXTERN_METHOD dispatch still lines up.
@objc(PearNotificationsModule)
class PearNotificationsModule: NSObject {
  // The bridge creates this instance itself; AppDelegate needs a handle to the live
  // instance to forward the APNs token/error it receives, so the module registers
  // itself here on init.
  static weak var shared: PearNotificationsModule?

  @objc static func requiresMainQueueSetup() -> Bool { true }

  private var pendingResolver: ((Any?) -> Void)?

  override init() {
    super.init()
    PearNotificationsModule.shared = self
  }

  @objc func isDevice(
    _ resolve: @escaping (Any?) -> Void,
    reject: @escaping (String, String, Error?) -> Void
  ) {
#if targetEnvironment(simulator)
    resolve(false)
#else
    resolve(true)
#endif
  }

  // Requests notification authorization, then (if granted) registers for
  // remote notifications and resolves once AppDelegate hands back the raw
  // APNs token via `PearNotificationsModule.didReceive(token:)`. Resolves
  // nil if the user denies authorization — register-and-forget, no retry.
  @objc func requestAndRegister(
    _ resolve: @escaping (Any?) -> Void,
    reject: @escaping (String, String, Error?) -> Void
  ) {
#if targetEnvironment(simulator)
    resolve(NSNull())
    return
#else
    UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
      guard granted else {
        resolve(NSNull())
        return
      }
      DispatchQueue.main.async {
        self.pendingResolver = resolve
        UIApplication.shared.registerForRemoteNotifications()
      }
    }
#endif
  }

  func didReceive(token: String) {
    pendingResolver?(token)
    pendingResolver = nil
  }

  func didFailToRegister() {
    pendingResolver?(NSNull())
    pendingResolver = nil
  }
}
