# Update code-signing cert

`updates-signing.pem` is the public self-signed X.509 certificate `expo-updates`
verifies manifest signatures against (referenced by `updates.codeSigningCertificate`
in `app.config.js`). **It is now committed** — the keypair is Terraform-generated
(`infra/modules/ec2_stack/main.tf`'s `tls_private_key.updates_signing` /
`tls_self_signed_cert.updates_signing`, mirrored in `infra/modules/app_stack/main.tf`),
not created by a local CLI step. The matching private key lives only in the
Terraform-owned `<name>-ota-secrets` Secrets Manager secret
(`UPDATES_SIGNING_PRIVATE_KEY`), never in this repo.

Re-materialize the committed public cert after a Terraform apply changes it
(first apply, or an intentional rotation) via:

```bash
terraform -chdir=infra output -raw updates_signing_certificate_pem > app/certs/updates-signing.pem
git add app/certs/updates-signing.pem && git commit -m "Update OTA code-signing certificate"
```

`UPDATES_SIGNING_KEY_ID` (defaults to `"main"` — `backend/app/config.py`) must match
`codeSigningMetadata.keyid` below it in `app.config.js`.

**Never regenerate this keypair once real builds are in the field** — a mismatched
public cert / private key pair bricks OTA for every installed client (manifests
fail signature verification, and the only recovery is a fresh native build with
the new cert baked in).
