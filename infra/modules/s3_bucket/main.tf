resource "aws_s3_bucket" "main" {
  bucket = var.name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "main" {
  bucket                  = aws_s3_bucket.main.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "main" {
  bucket = aws_s3_bucket.main.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.main.arn, "${aws_s3_bucket.main.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }],
      var.extra_bucket_policy_statements
    )
  })
  depends_on = [aws_s3_bucket_public_access_block.main]
}

resource "aws_s3_bucket_cors_configuration" "main" {
  count  = var.cors_origin != "" ? 1 : 0
  bucket = aws_s3_bucket.main.id
  cors_rule {
    allowed_methods = ["PUT", "POST", "GET", "HEAD"]
    allowed_origins = [var.cors_origin]
    allowed_headers = ["*"]
    expose_headers  = ["ETag", "Content-Length", "x-amz-server-side-encryption"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "main" {
  count  = (var.lifecycle_pending_expiry_days > 0 || var.lifecycle_expiry_days > 0) ? 1 : 0
  bucket = aws_s3_bucket.main.id

  dynamic "rule" {
    for_each = var.lifecycle_pending_expiry_days > 0 ? [1] : []
    content {
      id     = "expire-unconfirmed-uploads"
      status = "Enabled"
      filter {
        tag {
          key   = "status"
          value = "pending"
        }
      }
      expiration { days = var.lifecycle_pending_expiry_days }
    }
  }

  dynamic "rule" {
    for_each = var.lifecycle_expiry_days > 0 ? [1] : []
    content {
      id     = "expire-objects"
      status = "Enabled"
      filter { prefix = "" }
      expiration { days = var.lifecycle_expiry_days }
    }
  }
}
