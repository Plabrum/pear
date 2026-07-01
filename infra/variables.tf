variable "project_name" {
  description = "Project name - used as a prefix for all resource names"
  type        = string
  default     = "pear"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Must be staging or production."
  }
}

variable "deploy_target" {
  description = "Deploy target: ec2 (single instance + docker-compose) or ecs (Fargate + Aurora + Redis)"
  type        = string
  default     = "ec2"

  validation {
    condition     = contains(["ec2", "ecs"], var.deploy_target)
    error_message = "Must be ec2 or ecs."
  }
}

# -- EC2-specific (deploy_target = "ec2") --------------------------------------

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small"
}

variable "key_pair_name" {
  description = "EC2 key pair for SSH. Leave blank to use SSM Session Manager only."
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs permitted on port 22. Use [] to disable SSH entirely."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "domain" {
  description = "Root domain. Used for ACM cert, Route53 zone, CORS, SES. The API is served at api.<domain>."
  type        = string
  default     = "usepear.app"
}

variable "ecr_repository" {
  description = "ECR repository name"
  type        = string
  default     = "pear-api"
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "db_password" {
  description = "PostgreSQL master password - rotate via Secrets Manager after first deploy"
  type        = string
  sensitive   = true
}

variable "extra_env" {
  description = "Additional environment variables injected into ECS task definitions"
  type        = map(string)
  default     = {}
}
