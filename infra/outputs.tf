output "deploy_target" {
  description = "Active deploy target"
  value       = var.deploy_target
}

# EC2 outputs (empty when deploy_target = "ecs")
output "instance_id" {
  description = "EC2 instance ID (ec2 only)"
  value       = try(module.ec2[0].instance_id, "")
}

# Instance public IP (ephemeral - changes on stop/start). No EIP is allocated;
# the api.<domain> A-record in modules/ec2_stack tracks this value.
output "public_ip" {
  description = "EC2 public IP (ec2 only)"
  value       = try(module.ec2[0].public_ip, "")
}

# ECS outputs (empty when deploy_target = "ec2")
output "alb_dns_name" {
  description = "ALB DNS name (ecs only)"
  value       = try(module.ecs[0].alb_dns_name, "")
}

output "ecs_cluster_name" {
  description = "ECS cluster name (ecs only)"
  value       = try(module.ecs[0].ecs_cluster_name, "")
}

output "ecs_service_name" {
  description = "ECS API service name (ecs only)"
  value       = try(module.ecs[0].ecs_service_name, "")
}

output "worker_service_name" {
  description = "ECS worker service name (ecs only)"
  value       = try(module.ecs[0].worker_service_name, "")
}

# Shared outputs
output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.app.repository_url
}

output "app_secrets_arn" {
  description = "Secrets Manager ARN"
  value       = try(module.ec2[0].app_secrets_arn, try(module.ecs[0].app_secrets_arn, ""))
  sensitive   = true
}

output "s3_media_bucket" {
  description = "S3 media bucket name"
  value       = try(module.ec2[0].s3_media_bucket, try(module.ecs[0].s3_media_bucket, ""))
}

output "database_endpoint" {
  description = "Aurora write endpoint (ecs only)"
  value       = try(module.ecs[0].database_endpoint, "")
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint (ecs only)"
  value       = try(module.ecs[0].redis_endpoint, "")
  sensitive   = true
}

output "route53_nameservers" {
  description = "Nameservers to configure at your domain registrar"
  value       = aws_route53_zone.main.name_servers
}
