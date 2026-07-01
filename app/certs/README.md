# Update code-signing cert

`updates-signing.pem` (referenced by `updates.codeSigningCertificate` in
`app.config.js`) is **not yet present**. It needs to be generated before
self-hosted OTA can ship signed manifests.

**TODO (key provisioning owner):**

1. Generate an RSA keypair for `expo-updates` code signing, e.g.:
   ```bash
   npx expo-updates codesigning:generate \
     --key-output-directory ./certs \
     --certificate-output-directory ./certs \
     --certificate-validity-duration-years 10 \
     --certificate-common-name "Pear Updates"
   ```
2. Commit **only the public certificate** here as `updates-signing.pem`.
3. Keep the **private key** out of this repo entirely — it belongs only in
   the backend's secrets (`UPDATES_SIGNING_PRIVATE_KEY` in Secrets Manager /
   `.env`, see `backend/app/config.py`), matched by `UPDATES_SIGNING_KEY_ID`
   (defaults to `main`, matching `codeSigningMetadata.keyid` below).
4. Never regenerate the keypair once real builds are in the field — a
   mismatched public cert / private key pair bricks OTA for every installed
   client (manifests will fail signature verification).

Until step 2 lands, `app.config.js` points `codeSigningCertificate` at a
file that does not exist — `expo-updates` code-signing must be wired up
before this is relied upon in a real build.
