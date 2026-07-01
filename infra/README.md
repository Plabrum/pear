# infra/ — Terraform (single-EC2 deploy)

AWS infrastructure for **Pear**, managed with Terraform. One EC2 box runs the whole
stack via docker-compose (`api`, `worker`, `postgres`, `redis`, `caddy`), plus ECR,
S3 (media), SES, Secrets Manager, and Route53. The active path is
`deploy_target = "ec2"`. The ECS / Aurora path stays defined behind
`deploy_target = "ecs"` as the dormant one-variable scale-up.

> **Do NOT apply locally by habit.** The first `terraform apply` is manual and
> deliberate (it needs AWS credentials and a state bucket). Thereafter CI owns it
> via `.github/workflows/build-test-deploy.yml`.

Pear is **iOS-only** — there is no web frontend. Route53 hosts the zone for the
API (`api.<domain>`) and SES email records only. The app's own identity (slug
`wingmate`, bundle `com.plabrum.wingmate`, deep-link scheme) is not part of this
infra and is never renamed.

---

## Architecture

| Resource | Service | Notes |
|---|---|---|
| API + worker + db + redis + caddy | EC2 (`t3.small`) | Single box, docker-compose, auto-TLS via Caddy |
| Container registry | ECR (`pear-api`) | Images pushed by CI, last 10 retained |
| Media storage | S3 | Profile photos; lifecycle expiry on pending uploads |
| Secrets | Secrets Manager | `pear-production-app-secrets` — populated outside Terraform |
| Email | SES | Transactional (login codes, summaries) — `<domain>` identity |
| DNS | Route53 | `<domain>` zone — `api.<domain>` A-record → instance, SES records |
| Shell access | SSM Session Manager | No SSH keys / open ports — `just prod-ssh` |

State bucket and key are passed via `-backend-config` flags (see `scripts/tf-init.sh`),
not hard-coded in `main.tf` (`backend "s3" {}` is empty). Key: `pear/terraform.tfstate`.

---

## First Deploy

Run from the repo root unless noted. The helper `just` recipes wrap the common steps:
`just tf-init`, `just tf-plan`, `just tf-apply`, `just prod-ssh`.

### 1. Create the S3 state bucket + versioning (one-time)

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3api create-bucket --bucket tf-state-${ACCOUNT_ID} --region us-east-1
aws s3api put-bucket-versioning --bucket tf-state-${ACCOUNT_ID} \
  --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket tf-state-${ACCOUNT_ID} \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

`scripts/tf-init.sh` derives the same bucket name (`tf-state-<account-id>`, or
`tf-state-pear-<region>` when the account id can't be resolved).

### 2. Init the backend + select the workspace

```bash
just tf-init          # cd infra && ./scripts/tf-init.sh
# → terraform init -reconfigure with backend flags, then
#   terraform workspace select-or-create production
```

### 3. Plan + apply

```bash
# Set the DB master password for the first apply (rotate later via Secrets Manager):
export TF_VAR_db_password='change-me-now'

just tf-plan          # review the plan
just tf-apply         # creates ECR, Route53 zone, SES, EC2 box
```

The API container will crash-loop until an image exists in ECR — that is expected.
`db`, `redis`, and `caddy` come up; `api`/`worker` restart.

### 4. Set Route53 nameservers at the registrar

```bash
terraform -chdir=infra output route53_nameservers
```

Copy the four nameservers into the domain registrar's DNS settings. SES verification
and ACM/Caddy TLS can't complete until the zone is authoritative.

### 5. Populate Secrets Manager

Terraform creates the secret **empty** with `lifecycle { ignore_changes = [secret_string] }`,
so Terraform never overwrites real values. Populate once after first apply:

```bash
SECRET_ARN=$(terraform -chdir=infra output -raw app_secrets_arn)
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_ARN" \
  --secret-string '{
    "SECRET_KEY": "...",
    "JWT_SIGNING_KEY": "...",
    "APPLE_CLIENT_ID": "...",
    "APNS_KEY": "...",
    "APNS_KEY_ID": "...",
    "APNS_TEAM_ID": "..."
  }'
```

`deploy.sh` on the box merges this JSON into `/opt/pear/.env` on every deploy.
Pear self-hosts auth and storage.

### 6. Verify

```bash
just prod-ssh -- 'cd /opt/pear && docker compose ps'
```

`db`/`redis`/`caddy` up, `api`/`worker` restarting until the image lands.

---

## Backups

The entire Postgres database lives in one Docker named volume (`pgdata`) on one EBS
volume on one instance. This is the durability cost of the single-box model — the
ECS/Aurora path gets backups for free, but on EC2 they are our responsibility. Two
independent layers: logical (`pg_dump` → S3) and physical (EBS snapshots via DLM).

### Layer 1 — nightly `pg_dump` to S3

A logical dump is portable across Postgres versions and lets you restore a single
table. Two equivalent options:

**Option A — cron on the box** (simplest; lives in `user_data.sh`). Writes a
gzipped dump and copies it to the media/backups bucket, keeping the box's IAM role
(`s3:PutObject` on the bucket) as the only credential:

```bash
# /etc/cron.d/pear-pg-backup  — runs 03:17 UTC nightly
17 3 * * * root /opt/pear/backup-db.sh >> /var/log/pear-backup.log 2>&1
```

```bash
# /opt/pear/backup-db.sh
#!/bin/bash
set -euo pipefail
cd /opt/pear
source .env
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
KEY="db-backups/pear-${STAMP}.sql.gz"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip \
  | aws s3 cp - "s3://${S3_MEDIA_BUCKET}/${KEY}" --region "$AWS_REGION"
# Prune dumps older than 30 days
aws s3 ls "s3://${S3_MEDIA_BUCKET}/db-backups/" --region "$AWS_REGION" \
  | while read -r _ _ _ name; do
      created=$(echo "$name" | sed -E 's/pear-([0-9T]+Z)\.sql\.gz/\1/')
      [ "$created" \< "$(date -u -d '30 days ago' +%Y%m%dT%H%M%SZ)" ] \
        && aws s3 rm "s3://${S3_MEDIA_BUCKET}/db-backups/${name}" --region "$AWS_REGION"
    done
```

**Option B — SAQ scheduled task** (preferred once the backend is running). Register a
cron job in the worker that shells out to `pg_dump` and uploads via the app's S3
client. This keeps backup scheduling in the same place as the rest of the app's
background work and survives instance replacement without touching `user_data.sh`.
Keep S3 versioning enabled on the backups prefix so an overwrite is recoverable.

### Layer 2 — EBS snapshots via DLM

A volume-level snapshot captures the whole disk (Postgres data files, Docker
volumes, Caddy certs) and restores in minutes. Use a Data Lifecycle Manager policy
so AWS takes and prunes them automatically — no cron, no box involvement:

- **Target:** the root EBS volume, selected by tag (`Project=pear`).
- **Schedule:** daily, e.g. 04:00 UTC.
- **Retention:** keep 7 (one week). Bump for production once real data lands.

This is defined in Terraform alongside `ec2_stack` (DLM lifecycle policy + an IAM
role for the DLM service). Snapshots are crash-consistent; for a clean dump prefer
Layer 1, but DLM is the fast path back from instance loss.

### Restore procedure

**From a `pg_dump` (Layer 1)** — corrupted table, bad migration, or moving to a
fresh box:

```bash
# 1. Get a shell on the box
just prod-ssh

# 2. Pull the dump you want from S3
cd /opt/pear && source .env
aws s3 cp "s3://${S3_MEDIA_BUCKET}/db-backups/pear-<STAMP>.sql.gz" /tmp/restore.sql.gz

# 3. Stop the app so nothing writes mid-restore (leave db up)
docker compose stop api worker

# 4. Restore into a clean database
#    (drop+recreate to avoid merging into existing rows)
gunzip -c /tmp/restore.sql.gz \
  | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# 5. Bring the app back
docker compose up -d api worker
docker compose ps
```

**From an EBS snapshot (Layer 2)** — instance or volume loss:

1. In the console (or CLI), create a new gp3 volume from the chosen snapshot in the
   instance's AZ.
2. Stop the instance, detach the corrupt root volume, attach the restored volume as
   the root device (`/dev/xvda`), start the instance. *Or* launch a replacement
   instance from the snapshot and re-point DNS.
3. Because the `api` Route53 record tracks the instance's public IP (which is
   ephemeral), run `just tf-apply` after a stop/start so the A-record picks up the
   current IP.
4. `just prod-ssh -- 'cd /opt/pear && docker compose up -d && docker compose ps'`.

**Test the restore quarterly.** A backup you have never restored is a hypothesis,
not a backup. Restore the latest dump into a throwaway database (`createdb pear_restore_test`)
and spot-check row counts.

---

## Updating Secrets

Secrets are created by Terraform but intentionally **not updated** by it
(`lifecycle { ignore_changes = [secret_string] }`). Change them out of band:

```bash
aws secretsmanager put-secret-value \
  --secret-id pear-production-app-secrets \
  --secret-string '{"SECRET_KEY": "...", "JWT_SIGNING_KEY": "...", ...}'
just prod-ssh -- '/opt/pear/deploy.sh'   # re-merge into .env and restart
```

---

## SSM shell (no SSH)

```bash
just prod-ssh                 # interactive shell
just prod-ssh -- 'cd /opt/pear && docker compose logs -f api'
```

Resolves the instance from `terraform output instance_id`, falling back to the
`Name=pear*` tag. Requires `session-manager-plugin`
(`brew install --cask session-manager-plugin`).

---

## File Layout

```
infra/
├── main.tf              # Providers (AWS, random), module calls, outputs
├── variables.tf         # Input variables with defaults
├── shared.tf            # ECR, Route53 zone, SES identity + DKIM/SPF/DMARC/MX
├── scripts/
│   └── tf-init.sh       # Backend init + workspace select-or-create production
├── lambda/              # (reserved)
└── modules/
    ├── ec2_stack/       # ACTIVE: EC2 + SG + IAM + Secrets + S3 + user_data + compose
    ├── s3_bucket/       # Reusable media/backups bucket
    ├── app_stack/       # DORMANT: ECS/Aurora scale-up path (deploy_target = "ecs")
    ├── ecs_service/     # DORMANT
    └── networking/      # DORMANT: VPC/subnets for the ECS path
```

> **Vestigial in `app_stack` (ECS path only):** the SES inbound-email → S3 →
> `email_webhook` Lambda block (`aws_ses_receipt_rule*`, `aws_lambda_function.email_webhook`,
> `inbound_emails` bucket) is a support-inbox feature that **Pear does not
> use**. It reads `WEBHOOK_SECRET` from Secrets Manager — a key Pear never seeds (see the
> Secrets Manager block above; there is no `WEBHOOK_SECRET`). It is inert on the active
> `ec2` path (the whole `app_stack` module is dormant). If/when the ECS path is ever
> enabled, either drop that block from `app_stack/main.tf` or seed `WEBHOOK_SECRET` first,
> or the apply will fail resolving the missing secret key. Left in place deliberately to
> keep the validated `ecs` tree intact.
