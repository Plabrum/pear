output "instance_id" {
  description = "EC2 instance ID - used by the CI deploy workflow"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Instance public IP (ephemeral - the api.<domain> A-record points at this)"
  value       = aws_instance.app.public_ip
}

output "app_secrets_arn" {
  description = "Secrets Manager ARN - populate with real values after first apply"
  value       = aws_secretsmanager_secret.app.arn
  sensitive   = true
}

output "s3_media_bucket" {
  value = module.media.bucket_name
}

output "ses_configuration_set" {
  value = aws_ses_configuration_set.main.name
}
