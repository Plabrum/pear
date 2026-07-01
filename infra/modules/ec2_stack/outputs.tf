output "instance_id" {
  description = "EC2 instance ID - used by the CI deploy workflow"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Instance public IP (ephemeral - prefer eip_public_ip)"
  value       = aws_instance.app.public_ip
}

output "eip_public_ip" {
  description = "Elastic IP - stable address the api.<domain> A-record points at"
  value       = aws_eip.app.public_ip
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
