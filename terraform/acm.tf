# ACM 证书（区域 API Gateway 需要证书在同一区域）
# 注意：如果是 CloudFront + API Gateway，证书需要在 us-east-1
#      如果是 Regional API Gateway，证书需要在 API 所在区域

# 创建 ACM 证书（与 API Gateway 同一区域）
resource "aws_acm_certificate" "api" {
  domain_name       = "api.${var.domain_name}"
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}"  # 支持所有子域名
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-api-cert"
    Environment = var.environment
  }
}

# 在 Route53 中创建验证记录
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
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
resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# 获取 Route53 托管区域
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

