# Base variables - identical interface to app_stack for easy switching
variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }

variable "domain" {
  description = "Root domain. Used for Route53 zone, CORS, SES. The API is served at api.<domain>."
  type        = string
  default     = "usepear.app"
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID from shared resources"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL from shared resources"
  type        = string
}

variable "api_subdomain" {
  description = "Subdomain for the API"
  type        = string
  default     = "api"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "db_name" {
  type    = string
  default = "pear"
}

variable "db_username" {
  type    = string
  default = "postgres"
}

variable "db_password" {
  description = "Password for the local postgres container"
  type        = string
  sensitive   = true
}

variable "extra_env" {
  type    = map(string)
  default = {}
}

# -- EC2-specific --------------------------------------------------------------

variable "instance_type" {
  description = "t3.small (2 vCPU, 2 GB) comfortably runs postgres+redis+api+worker. t3.micro works with the swap configured in user_data.sh."
  type        = string
  default     = "t3.small"
}

variable "key_pair_name" {
  description = "EC2 key pair for SSH. Leave blank to use SSM Session Manager only."
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs permitted on port 22. Set to [] to disable SSH entirely."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "github_oidc_role_name" {
  description = "Name (not ARN) of the pre-existing GitHub Actions OIDC role. Leave blank to skip the read-only SSM/Secrets Manager grant (see ssm_params.tf)."
  type        = string
  default     = ""
}
