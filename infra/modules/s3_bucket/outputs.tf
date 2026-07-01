output "bucket_id" {
  description = "S3 bucket ID (name)"
  value       = aws_s3_bucket.main.id
}

output "bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.main.arn
}

output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.main.bucket
}

output "bucket_regional_domain_name" {
  description = "S3 bucket's regional domain name (e.g. <bucket>.s3.<region>.amazonaws.com) - CloudFront origin domain"
  value       = aws_s3_bucket.main.bucket_regional_domain_name
}
