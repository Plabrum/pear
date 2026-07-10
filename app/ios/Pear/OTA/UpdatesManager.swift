import Foundation
import Security
import CryptoKit
import os

// Custom OTA client — see docs/migration plan "Architecture: Custom Swift OTA
// client (Phase 6)". Replaces expo-updates entirely: this is Pear's own
// download/verify/apply/rollback system talking to the backend's plain-JSON
// `/updates/v2/manifest` protocol (see backend/app/platform/updates/routes.py).
final class UpdatesManager {
  static let shared = UpdatesManager()

  private let fileManager = FileManager.default
  private let logger = os.Logger(subsystem: "com.plabrum.pear.updates", category: "UpdatesManager")

  // Production only — DEBUG builds always load from Metro (see AppDelegate's
  // bundleURL()) and never reach this manager's download/apply path at all.
  private let manifestURL = URL(string: "https://api.usepear.app/updates/v2/manifest")!
  private let clientEventURL = URL(string: "https://api.usepear.app/updates/client-event")!

  private var runtimeVersion: String {
    Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown"
  }

  private var updatesDir: URL {
    let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
    return appSupport.appendingPathComponent("updates", isDirectory: true)
  }

  private var pointerURL: URL {
    updatesDir.appendingPathComponent("pointer.json")
  }

  private struct Pointer: Codable {
    var launchableUpdateUuid: String?
    var consecutiveFailedBoots: Int

    enum CodingKeys: String, CodingKey {
      case launchableUpdateUuid = "launchable_update_uuid"
      case consecutiveFailedBoots = "consecutive_failed_boots"
    }
  }

  // MARK: - Boot-time bundle resolution (synchronous, called from bundleURL())

  /// Reads the pointer file and does the rollback checkpoint. Must be fast and
  /// synchronous — this runs on the critical launch path before any JS exists.
  func launchBundleURL(embeddedURL: URL) -> URL {
    guard let pointer = readPointer(),
      let uuid = pointer.launchableUpdateUuid
    else {
      return embeddedURL
    }

    let bundlePath = updatesDir.appendingPathComponent(uuid).appendingPathComponent("bundle.js")
    guard fileManager.fileExists(atPath: bundlePath.path) else {
      writePointer(Pointer(launchableUpdateUuid: nil, consecutiveFailedBoots: 0))
      return embeddedURL
    }

    if pointer.consecutiveFailedBoots >= 1 {
      logger.warning("boot checkpoint: \(pointer.consecutiveFailedBoots) consecutive failed boots — rolling back to embedded bundle")
      writePointer(Pointer(launchableUpdateUuid: nil, consecutiveFailedBoots: 0))
      postClientEvent(event: "rolled_back", updateUuid: uuid, detail: "consecutive_failed_boots=\(pointer.consecutiveFailedBoots)")
      return embeddedURL
    }

    // Assume-failure-until-JS-proves-otherwise: increment and persist *before*
    // returning, so a crash/watchdog-kill/JS-fatal on this exact launch is
    // already reflected in the counter for the next cold launch.
    writePointer(Pointer(launchableUpdateUuid: uuid, consecutiveFailedBoots: pointer.consecutiveFailedBoots + 1))
    return bundlePath
  }

  /// Called once the JS side reaches an interactive screen — a more meaningful
  /// "this boot succeeded" signal than the old splash-hide effect.
  func markBootSuccessful() {
    guard var pointer = readPointer() else { return }
    guard pointer.consecutiveFailedBoots != 0 else { return }
    pointer.consecutiveFailedBoots = 0
    writePointer(pointer)
    if let uuid = pointer.launchableUpdateUuid {
      postClientEvent(event: "applied", updateUuid: uuid, detail: nil)
    }
  }

  func getCurrentUpdateInfo() -> [String: Any] {
    let pointer = readPointer()
    return [
      "updateUuid": pointer?.launchableUpdateUuid as Any? ?? NSNull(),
      "runtimeVersion": runtimeVersion,
      "isEmbedded": pointer?.launchableUpdateUuid == nil,
    ]
  }

  // MARK: - Check / download (fire-and-forget, called after launch completes)

  func checkForUpdate() {
    Task {
      await performCheck()
    }
  }

  private func performCheck() async {
    var components = URLComponents(url: manifestURL, resolvingAgainstBaseURL: false)!
    var queryItems = [
      URLQueryItem(name: "runtime_version", value: runtimeVersion),
      URLQueryItem(name: "channel", value: "production"),
      URLQueryItem(name: "platform", value: "ios"),
    ]
    if let current = readPointer()?.launchableUpdateUuid {
      queryItems.append(URLQueryItem(name: "current_update_id", value: current))
    }
    components.queryItems = queryItems

    guard let url = components.url else { return }

    let body: Data
    let response: URLResponse
    do {
      (body, response) = try await URLSession.shared.data(from: url)
    } catch {
      logger.error("manifest fetch failed: \(error.localizedDescription)")
      return
    }

    guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
      logger.error("manifest fetch returned non-200")
      return
    }

    guard verifySignature(body: body, response: http) else {
      logger.error("manifest signature verification FAILED — refusing to apply")
      postClientEvent(event: "verify_failed", updateUuid: nil, detail: "signature verification failed")
      return
    }

    guard let manifestResponse = try? JSONDecoder().decode(ManifestResponse.self, from: body) else {
      logger.error("manifest JSON decode failed")
      return
    }

    switch manifestResponse.status {
    case "no_update":
      return
    case "rollback":
      writePointer(Pointer(launchableUpdateUuid: nil, consecutiveFailedBoots: 0))
      return
    case "update_available":
      guard let manifest = manifestResponse.manifest else { return }
      guard manifest.runtimeVersion == runtimeVersion else {
        logger.error("manifest runtime_version mismatch: server=\(manifest.runtime_version_raw) client=\(self.runtimeVersion) — refusing to apply")
        return
      }
      await download(manifest: manifest)
    default:
      return
    }
  }

  // MARK: - Signature verification

  private func verifySignature(body: Data, response: HTTPURLResponse) -> Bool {
    guard let signatureB64 = response.value(forHTTPHeaderField: "x-update-signature") else {
      // Unsigned response — only the backend's local/dev/test config serves these
      // (no UPDATES_SIGNING_PRIVATE_KEY configured). Production always signs.
      logger.warning("manifest response unsigned — accepting only because this is not production config")
      return true
    }
    guard let signature = Data(base64Encoded: signatureB64),
      let publicKey = loadEmbeddedPublicKey()
    else {
      return false
    }

    var error: Unmanaged<CFError>?
    let verified = SecKeyVerifySignature(
      publicKey,
      .rsaSignatureMessagePKCS1v15SHA256,
      body as CFData,
      signature as CFData,
      &error
    )
    if let error {
      logger.error("SecKeyVerifySignature error: \(error.takeRetainedValue().localizedDescription)")
    }
    return verified
  }

  private func loadEmbeddedPublicKey() -> SecKey? {
    guard let certURL = Bundle.main.url(forResource: "updates-signing", withExtension: "pem"),
      let pemData = try? Data(contentsOf: certURL),
      let pemString = String(data: pemData, encoding: .utf8)
    else {
      return nil
    }

    let base64 = pemString
      .replacingOccurrences(of: "-----BEGIN CERTIFICATE-----", with: "")
      .replacingOccurrences(of: "-----END CERTIFICATE-----", with: "")
      .replacingOccurrences(of: "\n", with: "")

    guard let certData = Data(base64Encoded: base64),
      let certificate = SecCertificateCreateWithData(nil, certData as CFData)
    else {
      return nil
    }

    var trust: SecTrust?
    let policy = SecPolicyCreateBasicX509()
    guard SecTrustCreateWithCertificates(certificate, policy, &trust) == errSecSuccess,
      let trust
    else {
      return nil
    }
    return SecTrustCopyKey(trust)
  }

  // MARK: - Download + apply

  private func download(manifest: DecodedManifest) async {
    let tmpDir = updatesDir.appendingPathComponent("\(manifest.updateUuid).tmp", isDirectory: true)
    try? fileManager.removeItem(at: tmpDir)
    do {
      try fileManager.createDirectory(at: tmpDir, withIntermediateDirectories: true)
      try fileManager.createDirectory(at: tmpDir.appendingPathComponent("assets"), withIntermediateDirectories: true)
    } catch {
      logger.error("failed to create update dir: \(error.localizedDescription)")
      postClientEvent(event: "download_failed", updateUuid: manifest.updateUuid, detail: "mkdir failed")
      return
    }

    guard await downloadAndVerify(asset: manifest.launchAsset, to: tmpDir.appendingPathComponent("bundle.js")) else {
      postClientEvent(event: "download_failed", updateUuid: manifest.updateUuid, detail: "launch asset failed")
      try? fileManager.removeItem(at: tmpDir)
      return
    }

    for asset in manifest.assets {
      let ext = asset.fileExtension.map { ".\($0)" } ?? ""
      let dest = tmpDir.appendingPathComponent("assets").appendingPathComponent("\(asset.hash)\(ext)")
      guard await downloadAndVerify(asset: asset, to: dest) else {
        postClientEvent(event: "download_failed", updateUuid: manifest.updateUuid, detail: "asset \(asset.key) failed")
        try? fileManager.removeItem(at: tmpDir)
        return
      }
    }

    let finalDir = updatesDir.appendingPathComponent(manifest.updateUuid)
    do {
      try? fileManager.removeItem(at: finalDir)
      try fileManager.moveItem(at: tmpDir, to: finalDir)
    } catch {
      logger.error("failed to finalize update dir: \(error.localizedDescription)")
      postClientEvent(event: "download_failed", updateUuid: manifest.updateUuid, detail: "rename failed")
      return
    }

    writePointer(Pointer(launchableUpdateUuid: manifest.updateUuid, consecutiveFailedBoots: 0))
    logger.info("update \(manifest.updateUuid) downloaded and staged for next launch")

    garbageCollect(keeping: manifest.updateUuid)
  }

  private func downloadAndVerify(asset: DecodedAsset, to destination: URL) async -> Bool {
    guard let url = URL(string: asset.url) else { return false }
    let data: Data
    do {
      (data, _) = try await URLSession.shared.data(from: url)
    } catch {
      logger.error("asset download failed: \(error.localizedDescription)")
      return false
    }

    let digest = SHA256.hash(data: data)
    let hashB64URL = Data(digest).base64EncodedString()
      .replacingOccurrences(of: "+", with: "-")
      .replacingOccurrences(of: "/", with: "_")
      .replacingOccurrences(of: "=", with: "")

    guard hashB64URL == asset.hash else {
      logger.error("asset hash mismatch: expected=\(asset.hash) got=\(hashB64URL)")
      return false
    }

    do {
      try data.write(to: destination, options: .atomic)
      return true
    } catch {
      logger.error("asset write failed: \(error.localizedDescription)")
      return false
    }
  }

  // Keep the currently-launchable update + one previous — everything else is
  // stale bandwidth/disk that can never be pointed to again.
  private func garbageCollect(keeping currentUuid: String) {
    guard let entries = try? fileManager.contentsOfDirectory(at: updatesDir, includingPropertiesForKeys: [.contentModificationDateKey]) else {
      return
    }
    let dirs = entries.filter { $0.hasDirectoryPath && $0.lastPathComponent != currentUuid }
    let sorted = dirs.sorted { lhs, rhs in
      let lDate = (try? lhs.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
      let rDate = (try? rhs.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
      return lDate > rDate
    }
    for stale in sorted.dropFirst(1) {
      try? fileManager.removeItem(at: stale)
    }
  }

  // MARK: - Pointer file I/O

  private func readPointer() -> Pointer? {
    guard let data = try? Data(contentsOf: pointerURL) else { return nil }
    return try? JSONDecoder().decode(Pointer.self, from: data)
  }

  private func writePointer(_ pointer: Pointer) {
    do {
      try fileManager.createDirectory(at: updatesDir, withIntermediateDirectories: true)
      var dir = updatesDir
      var resourceValues = URLResourceValues()
      resourceValues.isExcludedFromBackup = true
      try? dir.setResourceValues(resourceValues)

      let data = try JSONEncoder().encode(pointer)
      try data.write(to: pointerURL, options: .atomic)
    } catch {
      logger.error("failed to write pointer.json: \(error.localizedDescription)")
    }
  }

  // MARK: - Server-visible logging

  private func postClientEvent(event: String, updateUuid: String?, detail: String?) {
    var request = URLRequest(url: clientEventURL)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    var body: [String: Any] = ["event": event, "runtime_version": runtimeVersion]
    if let updateUuid { body["update_uuid"] = updateUuid }
    if let detail { body["detail"] = detail }
    request.httpBody = try? JSONSerialization.data(withJSONObject: body)
    URLSession.shared.dataTask(with: request).resume()
  }
}

// MARK: - Manifest response decoding (mirrors backend/app/platform/updates/schemas.py)

private struct ManifestResponse: Decodable {
  let status: String
  let manifest: DecodedManifest?
}

private struct DecodedManifest: Decodable {
  let updateUuid: String
  let runtimeVersion: String
  let launchAsset: DecodedAsset
  let assets: [DecodedAsset]

  var runtime_version_raw: String { runtimeVersion }

  enum CodingKeys: String, CodingKey {
    case updateUuid = "update_uuid"
    case runtimeVersion = "runtime_version"
    case launchAsset = "launch_asset"
    case assets
  }
}

private struct DecodedAsset: Decodable {
  let key: String
  let url: String
  let hash: String
  let fileExtension: String?

  enum CodingKeys: String, CodingKey {
    case key, url, hash
    case fileExtension = "file_extension"
  }
}
