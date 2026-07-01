output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = module.api_service.service_name
}

output "worker_service_name" {
  value = module.worker_service.service_name
}

output "database_endpoint" {
  value     = aws_rds_cluster.main.endpoint
  sensitive = true
}

output "database_reader_endpoint" {
  value     = aws_rds_cluster.main.reader_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive = true
}

output "s3_media_bucket" {
  value = module.media.bucket_name
}

output "app_secrets_arn" {
  value     = aws_secretsmanager_secret.app.arn
  sensitive = true
}

output "vpc_id" {
  value = module.networking.vpc_id
}

output "private_subnet_ids" {
  value = module.networking.private_subnet_ids
}

output "ses_configuration_set" {
  value = aws_ses_configuration_set.main.name
}
