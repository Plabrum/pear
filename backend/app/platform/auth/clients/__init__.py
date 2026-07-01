"""External auth-provider clients (OTP + Apple identity verification).

Each has a Local/fake variant selected when ENV is local/testing (mirroring
`LocalEmailClient`): `LocalOtpClient` accepts a fixed dev code; the Apple verifier
accepts an injected test public key so a locally-signed token verifies without
hitting Apple's JWKS. Production selects the real Twilio Verify + JWKS variants.
"""
