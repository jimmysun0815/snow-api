# S3 Bucket for Collection Reports
resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-reports"

  tags = {
    Name        = "${var.project_name}-reports"
    Environment = var.environment
  }
}

# S3 Bucket 公开访问配置
resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# S3 Bucket Policy - 允许 CloudFront 访问
resource "aws_s3_bucket_policy" "reports" {
  bucket = aws_s3_bucket.reports.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontAccess"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.reports.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.reports.arn
          }
        }
      }
    ]
  })

  depends_on = [
    aws_s3_bucket.reports,
    aws_cloudfront_distribution.reports
  ]
}

# S3 Bucket Website 配置
resource "aws_s3_bucket_website_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "reports" {
  name                              = "${var.project_name}-reports-oac"
  description                       = "OAC for reports S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ACM 证书（用于 CloudFront，必须在 us-east-1）
resource "aws_acm_certificate" "reports" {
  provider          = aws.us_east_1
  domain_name       = "monitoring.steponsnow.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-reports-cert"
    Environment = var.environment
  }
}

# 自动验证 ACM 证书
resource "aws_route53_record" "reports_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.reports.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# 等待证书验证完成
resource "aws_acm_certificate_validation" "reports" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.reports.arn
  validation_record_fqdns = [for record in aws_route53_record.reports_cert_validation : record.fqdn]
}

# CloudFront Distribution for Reports
resource "aws_cloudfront_distribution" "reports" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Distribution for collection reports"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # 只使用北美和欧洲边缘节点
  aliases             = ["monitoring.steponsnow.com"]

  origin {
    domain_name              = aws_s3_bucket.reports.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.reports.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.reports.id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.reports.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 300   # 5 分钟
    max_ttl                = 3600  # 1 小时
    compress               = true
  }

  # 自定义错误响应
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.reports.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name        = "${var.project_name}-reports-cdn"
    Environment = var.environment
  }

  depends_on = [aws_acm_certificate_validation.reports]
}

# Route53 记录指向 CloudFront
resource "aws_route53_record" "reports" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "monitoring.steponsnow.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.reports.domain_name
    zone_id                = aws_cloudfront_distribution.reports.hosted_zone_id
    evaluate_target_health = false
  }
}

# IPv6 支持
resource "aws_route53_record" "reports_ipv6" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "monitoring.steponsnow.com"
  type    = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.reports.domain_name
    zone_id                = aws_cloudfront_distribution.reports.hosted_zone_id
    evaluate_target_health = false
  }
}

# 输出 CloudFront URL
output "reports_cloudfront_url" {
  description = "CloudFront distribution URL for reports"
  value       = "https://${aws_cloudfront_distribution.reports.domain_name}"
}

output "reports_custom_domain_url" {
  description = "Custom domain URL for reports"
  value       = "https://monitoring.steponsnow.com"
}

output "reports_s3_bucket" {
  description = "S3 bucket name for reports"
  value       = aws_s3_bucket.reports.id
}

