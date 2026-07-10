import Foundation
import AuthenticationServices

// Plain NSObject — see PearNotificationsModule.swift's header comment for why this
// doesn't conform to RCTBridgeModule directly (that's added via an Objective-C
// category in the companion .m file).
@objc(PearAppleAuthModule)
class PearAppleAuthModule: NSObject {
  @objc static func requiresMainQueueSetup() -> Bool { true }

  // Keeps the delegate alive for the duration of the auth flow — ASAuthorizationController
  // only holds a weak reference to its delegate/presentationContextProvider.
  private var activeDelegate: SignInDelegate?

  @objc func signIn(
    _ resolve: @escaping (Any?) -> Void,
    reject: @escaping (String, String, Error?) -> Void
  ) {
    DispatchQueue.main.async {
      let provider = ASAuthorizationAppleIDProvider()
      let request = provider.createRequest()
      request.requestedScopes = [.fullName, .email]

      let controller = ASAuthorizationController(authorizationRequests: [request])
      let delegate = SignInDelegate { [weak self] result in
        self?.activeDelegate = nil
        switch result {
        case .success(let payload):
          resolve(payload)
        case .cancelled:
          resolve(NSNull())
        case .failure(let error):
          reject("apple_signin_failed", error.localizedDescription, error)
        }
      }
      self.activeDelegate = delegate
      controller.delegate = delegate
      controller.presentationContextProvider = delegate
      controller.performRequests()
    }
  }
}

private enum SignInResult {
  case success([String: Any])
  case cancelled
  case failure(Error)
}

private class SignInDelegate: NSObject, ASAuthorizationControllerDelegate,
  ASAuthorizationControllerPresentationContextProviding
{
  private let completion: (SignInResult) -> Void

  init(completion: @escaping (SignInResult) -> Void) {
    self.completion = completion
  }

  func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
    UIApplication.shared.connectedScenes
      .compactMap { $0 as? UIWindowScene }
      .flatMap { $0.windows }
      .first { $0.isKeyWindow } ?? UIWindow()
  }

  func authorizationController(
    controller: ASAuthorizationController,
    didCompleteWithAuthorization authorization: ASAuthorization
  ) {
    guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
      let tokenData = credential.identityToken,
      let identityToken = String(data: tokenData, encoding: .utf8)
    else {
      completion(.failure(NSError(domain: "PearAppleAuth", code: 1, userInfo: [
        NSLocalizedDescriptionKey: "Apple sign-in did not return an identity token."
      ])))
      return
    }

    var payload: [String: Any] = ["identityToken": identityToken]
    // Exchanged server-side for a refresh token so the Apple grant can be revoked
    // on account deactivation. Non-fatal if absent — a cached-credential re-auth
    // may omit it; only the best-effort exchange step needs it.
    if let codeData = credential.authorizationCode,
      let authorizationCode = String(data: codeData, encoding: .utf8)
    {
      payload["authorizationCode"] = authorizationCode
    }
    if let given = credential.fullName?.givenName {
      payload["givenName"] = given
    }
    if let middle = credential.fullName?.middleName {
      payload["middleName"] = middle
    }
    if let family = credential.fullName?.familyName {
      payload["familyName"] = family
    }
    completion(.success(payload))
  }

  func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
    if let authError = error as? ASAuthorizationError, authError.code == .canceled {
      completion(.cancelled)
      return
    }
    completion(.failure(error))
  }
}
