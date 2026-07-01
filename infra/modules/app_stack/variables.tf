variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "domain" { type = string }

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID from shared resources"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL from shared resources"
  type        = string
}

variable "api_subdomain" {
  description = "Subdomain for the API (e.g. 'api' or 'api-staging')"
  type        = string
  default     = "api"
}

# -- Networking -----------------------------------------------------------------

variable "vpc_cidr" {
  type    = string
  default = "10.10.0.0/16"
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.10.1.0/24", "10.10.2.0/24"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.10.100.0/24", "10.10.101.0/24"]
}

# -- Image ----------------------------------------------------------------------

variable "image_tag" {
  type    = string
  default = "latest"
}

# -- Database -------------------------------------------------------------------

variable "db_name" {
  type    = string
  default = "pear"
}

variable "db_username" {
  type    = string
  default = "postgres"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "db_min_acu" {
  type    = number
  default = 0
}

variable "db_max_acu" {
  type    = number
  default = 4.0
}

variable "db_auto_pause_seconds" {
  type    = number
  default = 300
}

# -- Redis ----------------------------------------------------------------------

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

# -- ECS - API ------------------------------------------------------------------

variable "ecs_cpu" {
  type    = number
  default = 256
}

variable "ecs_memory" {
  type    = number
  default = 512
}

variable "ecs_desired_count" {
  type    = number
  default = 1
}

variable "ecs_min_capacity" {
  type    = number
  default = 1
}

variable "ecs_max_capacity" {
  type    = number
  default = 4
}

# -- ECS - Worker ---------------------------------------------------------------

variable "worker_cpu" {
  type    = number
  default = 256
}

variable "worker_memory" {
  type    = number
  default = 512
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

# -- Misc -----------------------------------------------------------------------

variable "extra_env" {
  type    = map(string)
  default = {}
}
