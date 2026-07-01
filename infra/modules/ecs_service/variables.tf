variable "name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "cluster_id" { type = string }
variable "image_url" { type = string }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "desired_count" { type = number }
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }

variable "environment_vars" {
  description = "List of {name, value} environment variable maps"
  type        = list(map(string))
  default     = []
}

variable "command" {
  description = "Override container entrypoint command. Empty list = use image default."
  type        = list(string)
  default     = []
}

variable "stop_timeout" {
  description = "Seconds ECS waits for graceful shutdown. 0 = use default."
  type        = number
  default     = 0
}

variable "container_name" {
  description = "Name of the container inside the task definition"
  type        = string
  default     = "app"
}

variable "container_port" {
  description = "Port the container listens on. 0 = no port mapping."
  type        = number
  default     = 0
}

variable "health_check_path" {
  description = "HTTP path for container health check. Empty string = no health check."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  type    = number
  default = 365
}

variable "target_group_arn" {
  description = "ALB target group ARN. Empty string = no load balancer attachment."
  type        = string
  default     = ""
}

variable "autoscaling_enabled" {
  type    = bool
  default = false
}

variable "autoscaling_min" {
  type    = number
  default = 1
}

variable "autoscaling_max" {
  type    = number
  default = 4
}

variable "autoscaling_cpu_target" {
  type    = number
  default = 70.0
}

variable "tags" {
  type    = map(string)
  default = {}
}
