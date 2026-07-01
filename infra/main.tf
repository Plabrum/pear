terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50, != 6.14.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    logtail = {
      source  = "BetterStackHQ/logtail"
      version = "~> 0.8"
    }
  }

  # Backend config is passed via -backend-config flags in CI (terraform.yml).
  # Bucket name is derived at runtime: tf-state-<aws-account-id>
  # Run locally: scripts/tf-init.sh (or pass flags manually)
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "pear"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# BetterStack/logtail is optional so `terraform validate`/`plan` works without a
# token. Production should set var.logtail_api_token to enable OTLP logging.
provider "logtail" {
  api_token = var.logtail_api_token
}

resource "logtail_source" "api" {
  count    = var.logtail_api_token != "" ? 1 : 0
  name     = "${var.project_name}-${var.environment}"
  platform = "open_telemetry"
}

# -- EC2 stack (deploy_target = "ec2") -----------------------------------------

module "ec2" {
  count  = var.deploy_target == "ec2" ? 1 : 0
  source = "./modules/ec2_stack"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  domain       = var.domain

  hosted_zone_id     = aws_route53_zone.main.zone_id
  ecr_repository_url = aws_ecr_repository.app.repository_url

  image_tag   = var.image_tag
  db_password = var.db_password
  extra_env   = var.extra_env

  instance_type     = var.instance_type
  key_pair_name     = var.key_pair_name
  ssh_allowed_cidrs = var.ssh_allowed_cidrs

  betterstack_otlp_ingesting_host = try(logtail_source.api[0].ingesting_host, "")
  betterstack_otlp_source_token   = try(logtail_source.api[0].token, "")
}

# -- ECS stack (deploy_target = "ecs") -----------------------------------------
# Dormant by default (deploy_target = "ec2"). The one-variable scale path.

module "ecs" {
  count  = var.deploy_target == "ecs" ? 1 : 0
  source = "./modules/app_stack"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  domain       = var.domain

  hosted_zone_id     = aws_route53_zone.main.zone_id
  ecr_repository_url = aws_ecr_repository.app.repository_url

  image_tag   = var.image_tag
  db_password = var.db_password
  extra_env   = var.extra_env

  betterstack_otlp_ingesting_host = try(logtail_source.api[0].ingesting_host, "")
  betterstack_otlp_source_token   = try(logtail_source.api[0].token, "")
}

# NOTE: Pear is iOS-only - there is no web frontend, so no Vercel provider,
# Vercel projects, or root/www/app DNS records. The api.<domain> A-record lives
# in the ec2_stack module (it points at the instance's public IP).
