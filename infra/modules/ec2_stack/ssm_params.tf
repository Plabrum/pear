# Dynamic config for ota.yml, fetched at CI runtime via the OIDC role it already
# assumes - no GitHub repo vars to keep in sync with Terraform state by hand.

locals {
  ssm_prefix = "/pear/${var.environment}/ota"
}

resource "aws_ssm_parameter" "s3_media_bucket" {
  name  = "${local.ssm_prefix}/s3_media_bucket"
  type  = "String"
  value = module.media.bucket_name
}

resource "aws_ssm_parameter" "api_base_url" {
  name  = "${local.ssm_prefix}/api_base_url"
  type  = "String"
  value = "https://${var.api_subdomain}.${var.domain}"
}

resource "aws_ssm_parameter" "cloudfront_domain" {
  name  = "${local.ssm_prefix}/cloudfront_domain"
  type  = "String"
  value = module.media_cdn.domain_name
}

resource "aws_ssm_parameter" "cloudfront_distribution_id" {
  name  = "${local.ssm_prefix}/cloudfront_distribution_id"
  type  = "String"
  value = module.media_cdn.distribution_id
}

resource "aws_ssm_parameter" "ota_secrets_arn" {
  name  = "${local.ssm_prefix}/ota_secrets_arn"
  type  = "String"
  value = aws_secretsmanager_secret.updates.arn
}

# -- Read-only grant on the pre-existing GitHub OIDC role -----------------------
# The OIDC role isn't a Terraform resource anywhere in this repo (it's referenced
# purely as secrets.OIDC_ROLE_ARN) - attach a policy to it BY NAME, without taking
# over its lifecycle. github_oidc_role_name is derived in CI from that same secret
# (an IAM role ARN's last path segment is the role name), so this needs no new
# GitHub secret.

data "aws_iam_role" "github_oidc" {
  count = var.github_oidc_role_name != "" ? 1 : 0
  name  = var.github_oidc_role_name
}

resource "aws_iam_role_policy" "github_oidc_ota_ci_read" {
  count = var.github_oidc_role_name != "" ? 1 : 0
  name  = "${local.name}-ota-ci-read"
  role  = data.aws_iam_role.github_oidc[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = [
          aws_ssm_parameter.s3_media_bucket.arn,
          aws_ssm_parameter.api_base_url.arn,
          aws_ssm_parameter.cloudfront_domain.arn,
          aws_ssm_parameter.cloudfront_distribution_id.arn,
          aws_ssm_parameter.ota_secrets_arn.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.updates.arn]
      },
    ]
  })
}
