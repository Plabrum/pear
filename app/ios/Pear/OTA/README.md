# Update code-signing cert

`updates-signing.pem` is the public self-signed X.509 certificate the custom Swift OTA
client verifies update manifests against. It's bundled into the app (picked up
automatically by XcodeGen's `sources:` scan of `Pear/`, no `subdirectory:` argument) and
loaded at runtime by `UpdatesManager.swift`'s `loadEmbeddedPublicKey()`
(`Bundle.main.url(forResource: "updates-signing", withExtension: "pem")`), which verifies
the `x-update-signature` response header against it (`SecKeyVerifySignature`, RSA
PKCS1v15 SHA256).

The keypair is Terraform-generated (`infra/modules/ec2_stack/main.tf`'s
`tls_private_key.updates_signing` / `tls_self_signed_cert.updates_signing`, mirrored in
`infra/modules/app_stack/main.tf`), not created by a local CLI step. The matching private
key lives only in the Terraform-owned `<name>-ota-secrets` Secrets Manager secret
(`UPDATES_SIGNING_PRIVATE_KEY`), never in this repo.

`UPDATES_SIGNING_KEY_ID` (defaults to `"main"` — `backend/app/config.py`) is the only
other place a key identifier needs to match; there's no `app.config.js` in the picture
post-off-Expo migration.

**Regeneration is CI/CD-only.** Per repo-wide Terraform policy, nobody runs
`terraform apply`/`output` against this stack locally — even with valid AWS credentials
on hand. If the cert ever needs to be re-materialized (first apply, or an intentional
rotation), that happens via the CI/CD pipeline, which would run the equivalent of:

```bash
terraform -chdir=infra output -raw updates_signing_certificate_pem > app/ios/Pear/OTA/updates-signing.pem
git add app/ios/Pear/OTA/updates-signing.pem && git commit -m "Update OTA code-signing certificate"
```

**Never regenerate this keypair once real builds are in the field** — a mismatched
public cert / private key pair bricks OTA for every installed client (manifests
fail signature verification, and the only recovery is a fresh native build with
the new cert baked in).
