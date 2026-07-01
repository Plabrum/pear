variable "name" {
  description = "Distribution/OAC name prefix (e.g. pear-production-media)"
  type        = string
}

variable "bucket_regional_domain_name" {
  description = "The origin S3 bucket's regional domain name (module.media.bucket_regional_domain_name)"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to the distribution"
  type        = map(string)
  default     = {}
}

variable "price_class" {
  description = "CloudFront price class. PriceClass_100 = US/Canada/Europe only (cheapest)."
  type        = string
  default     = "PriceClass_100"
}
