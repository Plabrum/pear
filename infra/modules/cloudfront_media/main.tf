# CloudFront in front of the media bucket, scoped (via the bucket policy statement
# the caller adds through s3_bucket's `extra_bucket_policy_statements`, conditioned
# on this distribution's ARN) to the `updates/*` prefix only — self-hosted OTA
# bundle/asset delivery (docs/migration/09-off-eas.md, 9b). The rest of the bucket
# (profile photos etc.) stays reachable only via presigned URLs, unchanged: this
# distribution can technically proxy any key a viewer requests, but the origin
# (S3) denies anything outside `updates/*` at the IAM layer regardless of what
# CloudFront is asked to fetch.

resource "aws_cloudfront_origin_access_control" "media" {
  name                              = "${var.name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "media" {
  enabled     = true
  comment     = "${var.name} - self-hosted OTA update assets (updates/* prefix only)"
  price_class = var.price_class

  origin {
    domain_name              = var.bucket_regional_domain_name
    origin_id                = var.name
    origin_access_control_id = aws_cloudfront_origin_access_control.media.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = var.name
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    # AWS managed "CachingOptimized" policy - long TTL, no cookies/query-string
    # forwarding. OTA assets are content-hashed (immutable per key), so this is
    # exactly the cache shape they want.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}
