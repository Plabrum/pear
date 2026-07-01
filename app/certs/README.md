# Update code-signing cert

`updates-signing.pem` is the public self-signed X.509 certificate `expo-updates`
verifies manifest signatures against (referenced by `updates.codeSigningCertificate`
in `app.config.js`). **It is now committed** — generated via:

```bash
npx expo-updates codesigning:generate \
  --key-output-directory <local, gitignored dir> \
  --certificate-output-directory <local, gitignored dir> \
  --certificate-validity-duration-years 10 \
  --certificate-common-name "Pear Updates"
```

The matching **private key never touched this repo** — it lives only in:
- `backend/.env.local` (gitignored) for local dev, as `UPDATES_SIGNING_PRIVATE_KEY`.
- AWS Secrets Manager for prod, same key name, populated out-of-band exactly like
  `SECRET_KEY`/`APPLE_CLIENT_ID`/`APNS_*` (see
  `infra/modules/ec2_stack/main.tf`'s `aws_secretsmanager_secret.app`).

`UPDATES_SIGNING_KEY_ID` (defaults to `"main"` — `backend/app/config.py`) must match
`codeSigningMetadata.keyid` below it in `app.config.js`.

**Never regenerate this keypair once real builds are in the field** — a mismatched
public cert / private key pair bricks OTA for every installed client (manifests
fail signature verification, and the only recovery is a fresh native build with
the new cert baked in).
