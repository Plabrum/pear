#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1

# ── System packages ───────────────────────────────────────────────────────────
dnf update -y
dnf install -y docker python3

# docker compose v2 plugin (not packaged on AL2023; install the binary)
COMPOSE_VERSION="v2.39.4"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/$${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

systemctl enable docker
systemctl start docker

systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# ── Swap ──────────────────────────────────────────────────────────────────────
# A 2 GB swapfile so a t3.micro (1 GB RAM) can run postgres+redis+api+worker+caddy
# together without the OOM killer. Harmless on the default t3.small. Idempotent —
# only created on first boot when /swapfile is absent.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q '^/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
fi

# ── App directory ─────────────────────────────────────────────────────────────
mkdir -p /opt/pear
cd /opt/pear

# ── docker-compose.yml — copied verbatim from the repo ───────────────────────
cat > /opt/pear/docker-compose.yml <<'COMPOSE'
${compose_content}
COMPOSE

# Caddyfile - copied verbatim from the repo
cat > /opt/pear/Caddyfile <<'CADDYFILE'
${caddyfile_content}
CADDYFILE

# ── .env — all non-secret config; secrets are merged in by deploy.sh ─────────
cat > /opt/pear/.env <<'ENV'
API_IMAGE=${ecr_repo_url}:${image_tag}
API_DOMAIN=${api_subdomain}.${domain}
POSTGRES_DB=${db_name}
POSTGRES_USER=${db_user}
POSTGRES_PASSWORD=${db_password}
DB_NAME=${db_name}
# Admin / owner role (DB_USER): the api/worker run `alembic upgrade head` as this
# role on start (scripts/start.sh), and the migrations create+grant the pear_app
# role and own the schema objects. ADMIN_DB_URL is built from DB_USER/DB_PASSWORD.
DB_USER=${db_user}
DB_PASSWORD=${db_password}
# App runtime role (DB_APP_USER): the NON-superuser, NON-owner login role the api
# and worker SERVE as (ASYNC_DATABASE_URL is built from DB_APP_USER/DB_APP_PASSWORD),
# so RLS is genuinely enforced. DB_APP_USER is non-secret and set here; the matching
# DB_APP_PASSWORD is a SECRET and is merged in from Secrets Manager by deploy.sh
# (do NOT commit it). Locally it defaults to `pear_app` (see app/config.py).
DB_APP_USER=pear_app
ENV=production
AWS_REGION=${aws_region}
S3_MEDIA_BUCKET=${s3_media_bucket}
APP_SECRETS_ARN=${secrets_arn}
DOMAIN=${domain}
SES_CONFIGURATION_SET=${ses_config_set}
FRONTEND_ORIGIN=${frontend_origin}
SUCCESS_REDIRECT_URL=${frontend_origin}
API_BASE_URL=${api_base_url}
BETTERSTACK_OTLP_INGESTING_HOST=${otlp_host}
BETTERSTACK_OTLP_SOURCE_TOKEN=${otlp_token}
%{ for k, v in extra_env ~}
${k}=${v}
%{ endfor ~}
ENV
chmod 600 /opt/pear/.env

# ── deploy.sh — pull latest image and restart; merge secrets into .env ────────
cat > /opt/pear/deploy.sh <<'DEPLOY'
#!/bin/bash
set -euo pipefail
cd /opt/pear

echo "==> ECR login"
aws ecr get-login-password --region ${aws_region} \
  | docker login --username AWS --password-stdin ${ecr_repo_url}

echo "==> Merging secrets into .env"
aws secretsmanager get-secret-value \
  --region ${aws_region} \
  --secret-id ${secrets_arn} \
  --query SecretString \
  --output text \
  | python3 -c "
import sys, json, os

env_path = '/opt/pear/.env'
env = {}
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip()

env.update(json.load(sys.stdin))

with open(env_path, 'w') as f:
    for k, v in env.items():
        f.write(f'{k}={v}\n')
os.chmod(env_path, 0o600)
"

echo "==> Pulling latest images"
docker compose pull api worker

echo "==> Starting stack"
docker compose up -d

echo "==> Stack status"
docker compose ps
DEPLOY
chmod +x /opt/pear/deploy.sh

# ── Systemd service ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/pear.service <<'SYSTEMD'
[Unit]
Description=Pear docker-compose stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/pear
ExecStart=/opt/pear/deploy.sh
ExecStop=/usr/bin/docker compose -f /opt/pear/docker-compose.yml down
TimeoutStartSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable pear
systemctl start pear || echo "First-boot deploy failed (image may not exist yet — will retry on next deploy)"

echo "==> user-data complete"
