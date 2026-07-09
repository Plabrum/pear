import React
import React_RCTAppDelegate
import ReactAppDependencyProvider
import UserNotifications

@main
class AppDelegate: RCTAppDelegate, UNUserNotificationCenterDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
  ) -> Bool {
    self.moduleName = "main"
    self.dependencyProvider = RCTAppDependencyProvider()
    self.initialProps = [:]

    UNUserNotificationCenter.current().delegate = self

    let result = super.application(application, didFinishLaunchingWithOptions: launchOptions)

#if !DEBUG
    // Fire-and-forget, after super.application(...) so it never blocks this
    // launch — checks/downloads apply on the *next* cold start via the pointer
    // file bundleURL() reads. DEBUG builds always load from Metro and never
    // reach this at all (see bundleURL() below).
    UpdatesManager.shared.checkForUpdate()
#endif

    return result
  }

  override func sourceURL(for bridge: RCTBridge) -> URL? {
    self.bundleURL()
  }

  override func bundleURL() -> URL? {
#if DEBUG
    return RCTBundleURLProvider.sharedSettings().jsBundleURL(forBundleRoot: "index")
#else
    let embedded = Bundle.main.url(forResource: "main", withExtension: "jsbundle")!
    return UpdatesManager.shared.launchBundleURL(embeddedURL: embedded)
#endif
  }

  override func application(
    _ application: UIApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
  ) {
    let hexToken = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
    PearNotificationsModule.shared?.didReceive(token: hexToken)
  }

  override func application(
    _ application: UIApplication,
    didFailToRegisterForRemoteNotificationsWithError error: Error
  ) {
    PearNotificationsModule.shared?.didFailToRegister()
  }

  // Present foreground pushes as a banner — iOS suppresses them by default while
  // the app is active, which read as "notifications arrive inconsistently."
  func userNotificationCenter(
    _ center: UNUserNotificationCenter,
    willPresent notification: UNNotification,
    withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
  ) {
    completionHandler([.banner, .list, .sound])
  }

  // Linking API
  override func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
  ) -> Bool {
    return super.application(app, open: url, options: options) || RCTLinkingManager.application(app, open: url, options: options)
  }

  // Universal Links
  override func application(
    _ application: UIApplication,
    continue userActivity: NSUserActivity,
    restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void
  ) -> Bool {
    let result = RCTLinkingManager.application(application, continue: userActivity, restorationHandler: restorationHandler)
    return super.application(application, continue: userActivity, restorationHandler: restorationHandler) || result
  }
}
