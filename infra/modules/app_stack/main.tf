data "aws_caller_identity" "current" {}

locals {
  name = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  inbound_emails_bucket_name = "${local.name}-inbound-emails-${random_id.bucket_suffix.hex}"

  # Built from the same inputs that produce module.media's bucket name/ARN, not
  # from module.media's own output — a module can't reference its own output as
  # one of its inputs, and this statement is itself an input to module.media.
  media_bucket_name = "${local.name}-media-${random_id.bucket_suffix.hex}"
  media_bucket_arn  = "arn:aws:s3:::${local.media_bucket_name}"
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# -
# NETWORKING
# -

module "networking" {
  source = "../networking"

  name                 = local.name
  aws_region           = var.aws_region
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  tags                 = local.common_tags
}

# -
# S3 STORAGE
# -

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

module "inbound_emails" {
  source = "../s3_bucket"

  name                  = local.inbound_emails_bucket_name
  tags                  = merge(local.common_tags, { Name = "${local.name}-inbound-emails", Purpose = "ses-inbound" })
  lifecycle_expiry_days = 365

  extra_bucket_policy_statements = [{
    Sid       = "AllowSESPuts"
    Effect    = "Allow"
    Principal = { Service = "ses.amazonaws.com" }
    Action    = "s3:PutObject"
    Resource  = "arn:aws:s3:::${local.inbound_emails_bucket_name}/emails/*"
    Condition = { StringEquals = { "aws:Referer" = data.aws_caller_identity.current.account_id } }
  }]
}

# -
# AURORA SERVERLESS V2
# -

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db-subnet-group"
  subnet_ids = module.networking.private_subnet_ids
  tags       = { Name = "${local.name}-db-subnet-group" }
}

resource "aws_rds_cluster_parameter_group" "main" {
  name        = "${local.name}-aurora-params"
  family      = "aurora-postgresql17"
  description = "Pear Aurora PostgreSQL parameters"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = { Name = "${local.name}-aurora-params" }
}

resource "aws_rds_cluster" "main" {
  cluster_identifier              = "${local.name}-aurora"
  engine                          = "aurora-postgresql"
  engine_mode                     = "provisioned"
  engine_version                  = "17.4"
  database_name                   = var.db_name
  master_username                 = var.db_username
  master_password                 = var.db_password
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [module.networking.database_sg_id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.main.name

  serverlessv2_scaling_configuration {
    min_capacity             = var.db_min_acu
    max_capacity             = var.db_max_acu
    seconds_until_auto_pause = var.db_auto_pause_seconds
  }

  backup_retention_period   = var.environment == "production" ? 7 : 1
  preferred_backup_window   = "03:00-04:00"
  storage_encrypted         = true
  deletion_protection       = var.environment == "production"
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.name}-final-snapshot" : null

  tags = { Name = "${local.name}-aurora" }
}

resource "aws_rds_cluster_instance" "main" {
  identifier         = "${local.name}-aurora-instance"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  db_subnet_group_name         = aws_db_subnet_group.main.name
  publicly_accessible          = false
  performance_insights_enabled = true

  tags = { Name = "${local.name}-aurora-instance" }
}

# -
# SECRETS MANAGER
# -

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name}-app-secrets"
  description             = "Pear application secrets - managed outside Terraform after initial creation"
  recovery_window_in_days = 7
  tags                    = { Name = "${local.name}-app-secrets" }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  # Seed placeholders only. Real values are set out-of-band (console/CLI/CI) and
  # preserved by the ignore_changes lifecycle below — Terraform never overwrites them.
  secret_string = jsonencode({
    SECRET_KEY      = "CHANGE-ME"
    APPLE_CLIENT_ID = "CHANGE-ME"
    APNS_KEY        = ""
    APNS_KEY_ID     = ""
    APNS_TEAM_ID    = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Separate secret for the OTA publish token + code-signing private key - kept
# apart from aws_secretsmanager_secret.app (which has ignore_changes = [secret_string]
# above) so Terraform can fully own its contents, generated fresh, no manual sync.

resource "random_password" "updates_publish_token" {
  length  = 48
  special = false # bearer token in an Authorization header - keep header-safe
}

resource "tls_private_key" "updates_signing" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "updates_signing" {
  private_key_pem = tls_private_key.updates_signing.private_key_pem

  subject {
    common_name = "Pear Updates"
  }

  validity_period_hours = 24 * 365 * 10
  allowed_uses          = ["digital_signature", "key_encipherment"]
  is_ca_certificate     = false
}

resource "aws_secretsmanager_secret" "updates" {
  name                    = "${local.name}-ota-secrets"
  description             = "Terraform-owned OTA publish token + code-signing private key - fully managed, no manual sync"
  recovery_window_in_days = var.environment == "production" ? 7 : 0
  tags                    = { Name = "${local.name}-ota-secrets" }
}

resource "aws_secretsmanager_secret_version" "updates" {
  secret_id = aws_secretsmanager_secret.updates.id

  # No ignore_changes - Terraform is the sole owner of this secret's contents.
  secret_string = jsonencode({
    UPDATES_PUBLISH_TOKEN = random_password.updates_publish_token.result
    # base64-encoded so the PEM's embedded newlines never round-trip through
    # deploy.sh's single-line .env merge - decoded back to PEM in signing.py.
    UPDATES_SIGNING_PRIVATE_KEY = base64encode(tls_private_key.updates_signing.private_key_pem)
  })
}

# -
# IAM
# -

# Execution role - ECS control plane (pull images, write logs, read secrets)
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name}-ecs-task-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = { Name = "${local.name}-ecs-task-execution" }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${local.name}-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.app.arn, aws_secretsmanager_secret.updates.arn]
    }]
  })
}

# Task role - application code permissions at runtime
resource "aws_iam_role" "ecs_task" {
  name = "${local.name}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = { Name = "${local.name}-ecs-task" }
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "${local.name}-task-policy"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 - media uploads (presigned POST/GET; tagging to clear status=pending lifecycle marker)
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
      # S3 - inbound emails (worker reads raw MIME)
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          module.inbound_emails.bucket_arn,
          "${module.inbound_emails.bucket_arn}/*",
        ]
      },
      # Secrets Manager
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.app.arn]
      },
      # SES - outbound email
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail", "ses:SendTemplatedEmail"]
        Resource = ["*"]
      },
      # SSM Messages - ECS Exec (SSH into tasks via Session Manager)
      {
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel",
        ]
        Resource = ["*"]
      },
    ]
  })
}

# -
# ECS CLUSTER
# -

resource "aws_ecs_cluster" "main" {
  name = "${local.name}-cluster"
  tags = { Name = "${local.name}-cluster" }
}

# -
# APPLICATION LOAD BALANCER
# -

resource "aws_lb" "main" {
  name               = "${local.name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.networking.alb_sg_id]
  subnets            = module.networking.public_subnet_ids

  enable_deletion_protection = var.environment == "production"

  tags = { Name = "${local.name}-alb" }
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.networking.vpc_id
  target_type = "ip"

  deregistration_delay = 30

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name}-api-tg" }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.api.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# -
# ACM CERTIFICATE + ROUTE53 API RECORD
# -

resource "aws_acm_certificate" "api" {
  domain_name       = "${var.api_subdomain}.${var.domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name}-api-cert" }
}

resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.hosted_zone_id
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.api_cert_validation : record.fqdn]
}

resource "aws_route53_record" "api" {
  zone_id = var.hosted_zone_id
  name    = "${var.api_subdomain}.${var.domain}"
  type    = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# -
# ECS SERVICES
# -

module "api_service" {
  source = "../ecs_service"

  name        = "${local.name}-api"
  environment = var.environment
  aws_region  = var.aws_region
  cluster_id  = aws_ecs_cluster.main.id
  image_url   = "${var.ecr_repository_url}:${var.image_tag}"

  cpu           = var.ecs_cpu
  memory        = var.ecs_memory
  desired_count = var.ecs_desired_count

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  subnet_ids         = module.networking.public_subnet_ids
  security_group_ids = [module.networking.ecs_tasks_sg_id]

  container_name    = "app"
  container_port    = 8000
  health_check_path = "/health"

  environment_vars = concat([
    { name = "ENV", value = var.environment },
    { name = "DB_ENDPOINT", value = aws_rds_cluster.main.endpoint },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_USER", value = var.db_username },
    { name = "DB_PASSWORD", value = var.db_password },
    { name = "REDIS_URL", value = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379" },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "S3_MEDIA_BUCKET", value = module.media.bucket_name },
    { name = "S3_INBOUND_EMAIL_BUCKET", value = module.inbound_emails.bucket_name },
    { name = "APP_SECRETS_ARN", value = aws_secretsmanager_secret.app.arn },
    { name = "SES_CONFIGURATION_SET", value = aws_ses_configuration_set.main.name },
    { name = "DOMAIN", value = var.domain },
    { name = "FRONTEND_ORIGIN", value = "https://app.${var.domain}" },
    { name = "SUCCESS_REDIRECT_URL", value = "https://app.${var.domain}" },
    { name = "API_BASE_URL", value = "https://${var.api_subdomain}.${var.domain}" },
  ], [for k, v in var.extra_env : { name = k, value = v }])

  secrets = [
    { name = "UPDATES_PUBLISH_TOKEN", valueFrom = "${aws_secretsmanager_secret.updates.arn}:UPDATES_PUBLISH_TOKEN::" },
    { name = "UPDATES_SIGNING_PRIVATE_KEY", valueFrom = "${aws_secretsmanager_secret.updates.arn}:UPDATES_SIGNING_PRIVATE_KEY::" },
  ]

  target_group_arn = aws_lb_target_group.api.arn

  autoscaling_enabled    = true
  autoscaling_min        = var.ecs_min_capacity
  autoscaling_max        = var.ecs_max_capacity
  autoscaling_cpu_target = 70.0

  tags = local.common_tags

  depends_on = [aws_lb_listener.https]
}

module "worker_service" {
  source = "../ecs_service"

  name        = "${local.name}-worker"
  environment = var.environment
  aws_region  = var.aws_region
  cluster_id  = aws_ecs_cluster.main.id
  image_url   = "${var.ecr_repository_url}:${var.image_tag}"

  cpu           = var.worker_cpu
  memory        = var.worker_memory
  desired_count = var.worker_desired_count

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  subnet_ids         = module.networking.public_subnet_ids
  security_group_ids = [module.networking.ecs_tasks_sg_id]

  container_name = "worker"
  command        = ["./scripts/start-worker.sh"]
  stop_timeout   = 60

  environment_vars = concat([
    { name = "ENV", value = var.environment },
    { name = "DB_ENDPOINT", value = aws_rds_cluster.main.endpoint },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_USER", value = var.db_username },
    { name = "DB_PASSWORD", value = var.db_password },
    { name = "REDIS_URL", value = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379" },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "S3_MEDIA_BUCKET", value = module.media.bucket_name },
    { name = "S3_INBOUND_EMAIL_BUCKET", value = module.inbound_emails.bucket_name },
    { name = "APP_SECRETS_ARN", value = aws_secretsmanager_secret.app.arn },
    { name = "DOMAIN", value = var.domain },
  ], [for k, v in var.extra_env : { name = k, value = v }])

  secrets = [
    { name = "UPDATES_PUBLISH_TOKEN", valueFrom = "${aws_secretsmanager_secret.updates.arn}:UPDATES_PUBLISH_TOKEN::" },
    { name = "UPDATES_SIGNING_PRIVATE_KEY", valueFrom = "${aws_secretsmanager_secret.updates.arn}:UPDATES_SIGNING_PRIVATE_KEY::" },
  ]

  tags = local.common_tags
}

# -
# ELASTICACHE REDIS
# -

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis-subnet-group"
  subnet_ids = module.networking.private_subnet_ids
  tags       = { Name = "${local.name}-redis-subnet-group" }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis-enc"
  description          = "Pear Redis - sessions and background queue (encrypted)"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_clusters   = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [module.networking.redis_sg_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  maintenance_window       = "sun:05:00-sun:06:00"
  snapshot_retention_limit = var.environment == "production" ? 1 : 0

  tags = { Name = "${local.name}-redis" }
}

# -
# SES - PER-ENVIRONMENT
# -

resource "aws_ses_configuration_set" "main" {
  name = "${local.name}-ses"
}

resource "aws_ses_receipt_rule_set" "main" {
  rule_set_name = "${local.name}-receipt-rules"
}

# NOTE: Only one rule set can be active per region. When a staging env is added,
# move this to shared.tf with a combined rule set covering both environments.
resource "aws_ses_active_receipt_rule_set" "main" {
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name
}

resource "aws_ses_receipt_rule" "inbound" {
  name          = "${local.name}-inbound-email"
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name
  enabled       = true
  scan_enabled  = true

  # Domain-wide catch-all: SES routes anything@<domain> through this rule.
  # Per-recipient routing happens in process_inbound_email_task.
  recipients = [var.domain]

  s3_action {
    bucket_name       = module.inbound_emails.bucket_id
    object_key_prefix = "emails/"
    position          = 1
  }

  depends_on = [module.inbound_emails]
}

# -
# LAMBDA - Inbound email S3--webhook forwarder
# -

data "archive_file" "email_webhook_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../lambda/handler.py"
  output_path = "${path.module}/../../../lambda/email_webhook.zip"
}

resource "aws_iam_role" "email_webhook_lambda" {
  name = "${local.name}-email-webhook-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = { Name = "${local.name}-email-webhook-lambda" }
}

resource "aws_iam_role_policy_attachment" "email_webhook_lambda_basic" {
  role       = aws_iam_role.email_webhook_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "email_webhook_lambda_s3" {
  name = "${local.name}-email-webhook-s3"
  role = aws_iam_role.email_webhook_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "${module.inbound_emails.bucket_arn}/emails/*"
    }]
  })
}

data "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
}

resource "aws_lambda_function" "email_webhook" {
  function_name    = "${local.name}-email-webhook"
  filename         = data.archive_file.email_webhook_zip.output_path
  source_code_hash = data.archive_file.email_webhook_zip.output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  role             = aws_iam_role.email_webhook_lambda.arn
  timeout          = 30

  environment {
    variables = {
      WEBHOOK_URL    = "https://${var.api_subdomain}.${var.domain}/webhooks/comms/email/inbound"
      WEBHOOK_SECRET = jsondecode(data.aws_secretsmanager_secret_version.app.secret_string)["WEBHOOK_SECRET"]
    }
  }

  tags = { Name = "${local.name}-email-webhook" }
}

resource "aws_cloudwatch_log_group" "email_webhook_lambda" {
  name              = "/aws/lambda/${aws_lambda_function.email_webhook.function_name}"
  retention_in_days = 365
  tags              = { Name = "${local.name}-email-webhook-logs" }
}

resource "aws_lambda_permission" "s3_invoke_email_webhook" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.email_webhook.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = module.inbound_emails.bucket_arn
}

resource "aws_s3_bucket_notification" "inbound_emails" {
  bucket = module.inbound_emails.bucket_id

  lambda_function {
    lambda_function_arn = aws_lambda_function.email_webhook.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "emails/"
  }

  depends_on = [aws_lambda_permission.s3_invoke_email_webhook]
}
