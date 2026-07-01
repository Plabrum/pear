locals {
  name = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# -- AMI -----------------------------------------------------------------------
# Amazon Linux 2023 x86_64 - matches the linux/amd64 CI build target
#
# "al2023-ami-*-x86_64" also matches the "minimal" variant
# (al2023-ami-minimal-2023...), which doesn't ship amazon-ssm-agent
# preinstalled - user_data.sh's `systemctl start amazon-ssm-agent` then
# aborts the whole boot script under set -e, and the instance never
# registers with SSM. Standard AMI names start with the date
# (al2023-ami-2023...), so anchoring on a digit excludes "minimal".

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# -- S3 ------------------------------------------------------------------------

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  # Built from the same inputs that produce module.media's bucket name/ARN, not
  # from module.media's own output — a module can't reference its own output as
  # one of its inputs, and this statement is itself an input to module.media.
  media_bucket_name = "${local.name}-media-${random_id.bucket_suffix.hex}"
  media_bucket_arn  = "arn:aws:s3:::${local.media_bucket_name}"
}

module "media" {
  source = "../s3_bucket"

  name        = local.media_bucket_name
  tags        = merge(local.common_tags, { Name = "${local.name}-media", Purpose = "media-uploads" })
  cors_origin = "https://app.${var.domain}"

  lifecycle_pending_expiry_days = 1

  # Scopes CloudFront's OAC read access to the `updates/*` prefix only (self-hosted
  # OTA bundle/asset delivery, docs/migration/09-off-eas.md 9b) — everything else
  # in the bucket (profile photos) stays reachable only via presigned URLs,
  # exactly as before this existed. The `AWS:SourceArn` condition means this grant
  # is useless to any CloudFront distribution other than media_cdn specifically,
  # even though the Principal is the whole `cloudfront.amazonaws.com` service.
  extra_bucket_policy_statements = [{
    Sid       = "AllowCloudFrontOACReadUpdatesPrefix"
    Effect    = "Allow"
    Principal = { Service = "cloudfront.amazonaws.com" }
    Action    = "s3:GetObject"
    Resource  = "${local.media_bucket_arn}/updates/*"
    Condition = { StringEquals = { "AWS:SourceArn" = module.media_cdn.distribution_arn } }
  }]
}

# -- CloudFront (self-hosted OTA update delivery) -------------------------------

module "media_cdn" {
  source = "../cloudfront_media"

  name                        = "${local.name}-media"
  bucket_regional_domain_name = module.media.bucket_regional_domain_name
  tags                        = merge(local.common_tags, { Name = "${local.name}-media-cdn" })
}

# -- Secrets Manager -----------------------------------------------------------
# Created with placeholder values by Terraform; populate after first apply:
#   aws secretsmanager put-secret-value --secret-id <arn> --secret-string '{"SECRET_KEY":"..."}'
# deploy.sh refreshes the box's .env from here on every deploy.

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name}-app-secrets"
  description             = "Pear ${var.environment} secrets - populate manually after first apply"
  recovery_window_in_days = var.environment == "production" ? 7 : 0

  tags = { Name = "${local.name}-app-secrets" }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id

  # Pear's app secrets. All placeholders - populate real values out of band after
  # first apply. Auth is magic-link + Apple; Pear self-hosts auth and push.
  secret_string = jsonencode({
    SECRET_KEY      = "CHANGE-ME" # Litestar session signing secret (signs the session cookie)
    APPLE_CLIENT_ID = "CHANGE-ME" # Apple Sign-In `aud`
    APNS_KEY        = ""          # APNs auth key (.p8 contents) - push
    APNS_KEY_ID     = ""          # APNs key ID - push
    APNS_TEAM_ID    = ""          # Apple team ID - push
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# -- SES -----------------------------------------------------------------------

resource "aws_ses_configuration_set" "main" {
  name = "${local.name}-ses"
}

# -- Security group ------------------------------------------------------------

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "${local.name} EC2 - HTTP/HTTPS public, SSH restricted"

  ingress {
    description = "HTTP (Caddy ACME + redirect)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  dynamic "ingress" {
    for_each = length(var.ssh_allowed_cidrs) > 0 ? [1] : []
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.ssh_allowed_cidrs
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-app" })
}

# -- IAM -----------------------------------------------------------------------

resource "aws_iam_role" "app" {
  name = "${local.name}-ec2"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge(local.common_tags, { Name = "${local.name}-ec2" })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "app" {
  name = "${local.name}-ec2-policy"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.app.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail", "ses:SendTemplatedEmail"]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetObjectTagging",
          "s3:PutObjectTagging",
          "s3:DeleteObjectTagging",
        ]
        Resource = [
          module.media.bucket_arn,
          "${module.media.bucket_arn}/*",
        ]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name}-ec2"
  role = aws_iam_role.app.name
}

# -- EC2 instance --------------------------------------------------------------

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.app.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null
  vpc_security_group_ids = [aws_security_group.app.id]

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    compose_content   = file("${path.module}/docker-compose.yml")
    caddyfile_content = file("${path.module}/Caddyfile")
    aws_region        = var.aws_region
    ecr_repo_url      = var.ecr_repository_url
    image_tag         = var.image_tag
    domain            = var.domain
    api_subdomain     = var.api_subdomain
    db_name           = var.db_name
    db_user           = var.db_username
    db_password       = var.db_password
    secrets_arn       = aws_secretsmanager_secret.app.arn
    ses_config_set    = aws_ses_configuration_set.main.name
    s3_media_bucket   = module.media.bucket_name
    frontend_origin   = "https://app.${var.domain}"
    api_base_url      = "https://${var.api_subdomain}.${var.domain}"
    extra_env         = var.extra_env
  }))

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = merge(local.common_tags, { Name = "${local.name}-app" })

  # user_data only runs at first boot - replace instance if it changes
  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

# -- Route53 -------------------------------------------------------------------
# Points api.<domain> at the instance's public IP. The IP is ephemeral (changes
# on stop/start), so re-apply after a stop/start to refresh the A-record.

resource "aws_route53_record" "api" {
  zone_id = var.hosted_zone_id
  name    = "${var.api_subdomain}.${var.domain}"
  type    = "A"
  ttl     = 60
  records = [aws_instance.app.public_ip]
}
