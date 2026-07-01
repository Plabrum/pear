variable "name" {
  description = "Full bucket name (including any random suffix)"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to the bucket"
  type        = map(string)
  default     = {}
}

variable "cors_origin" {
  description = "Allowed CORS origin (e.g. https://app.example.com). Omit to skip CORS config."
  type        = string
  default     = ""
}

variable "lifecycle_pending_expiry_days" {
  description = "Days before objects tagged status=pending are deleted (presigned upload cleanup). 0 = disabled."
  type        = number
  default     = 0
}

variable "lifecycle_expiry_days" {
  description = "Days before all objects are deleted (e.g. raw inbound emails). 0 = disabled."
  type        = number
  default     = 0
}

variable "extra_bucket_policy_statements" {
  description = "Additional IAM policy statements merged into the bucket policy alongside the HTTPS-only deny."
  type        = list(any)
  default     = []
}
