output "domain_name" {
  description = "CloudFront distribution domain (vars.CLOUDFRONT_DOMAIN in ota.yml)"
  value       = aws_cloudfront_distribution.media.domain_name
}

output "distribution_id" {
  description = "CloudFront distribution ID (vars.CLOUDFRONT_DISTRIBUTION_ID in ota.yml, for invalidation)"
  value       = aws_cloudfront_distribution.media.id
}

output "distribution_arn" {
  description = "CloudFront distribution ARN - used to scope the media bucket's OAC policy statement"
  value       = aws_cloudfront_distribution.media.arn
}
