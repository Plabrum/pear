# Base variables - identical interface to app_stack for easy switching
variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }

variable "domain" {
  description = "Root domain. Used for Route53 zone, CORS, SES. The API is served at api.<domain>."
  type        = string
  default     = "pear.dev" # TODO: set to Pear's real domain before first apply
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

# -- BetterStack / logtail (optional) ------------------------------------------
# Centralized OTLP log shipping. Optional so `terraform validate`/`plan` works
# without a token. Prod should set betterstack_otlp_source_token (single-box
# logs are otherwise lost on instance replacement).
variable "betterstack_otlp_ingesting_host" {
  type    = string
  default = ""
}
variable "betterstack_otlp_source_token" {
  type      = string
  sensitive = true
  default   = ""
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
