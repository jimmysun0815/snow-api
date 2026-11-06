# API Gateway 输出
output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = "${aws_api_gateway_stage.main.invoke_url}"
}

output "api_custom_domain_url" {
  description = "自定义域名 API URL"
  value       = "https://api.${var.domain_name}"
}

output "api_gateway_stage" {
  description = "API Gateway stage name"
  value       = aws_api_gateway_stage.main.stage_name
}

output "acm_certificate_status" {
  description = "ACM 证书状态"
  value       = aws_acm_certificate.api.status
}

# Lambda 输出
output "lambda_api_function_name" {
  description = "API Lambda function name"
  value       = aws_lambda_function.api.function_name
}

output "lambda_collector_function_name" {
  description = "Collector Lambda function name"
  value       = aws_lambda_function.collector.function_name
}

# S3 输出
output "lambda_artifacts_bucket" {
  description = "S3 bucket for Lambda artifacts"
  value       = aws_s3_bucket.lambda_artifacts.id
}

# VPC 输出
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

# 部署命令提示
output "deployment_info" {
  description = "Deployment information"
  value = <<-EOT
    ✅ 部署完成！

    📡 API 地址:
       自定义域名: https://api.${var.domain_name}/api/resorts
       默认地址: ${aws_api_gateway_stage.main.invoke_url}/api/resorts

    🔒 TLS 证书:
       状态: ${aws_acm_certificate.api.status}
       域名: api.${var.domain_name}, *.${var.domain_name}

    🗄️  数据库: Supabase（见 docs/SUPABASE_CUTOVER.md）

    🔧 下一步:
       1. 采集数据: 手动触发 ${aws_lambda_function.collector.function_name}
       2. 测试 API: curl https://api.${var.domain_name}/api/resorts/summary

    📊 监控:
       CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#logsV2:log-groups
  EOT
}

