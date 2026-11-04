# Lambda 函数 - Trail Collector (雪道数据采集)
resource "aws_lambda_function" "trails_collector" {
  function_name = "${var.project_name}-trails-collector"
  role          = aws_iam_role.lambda_exec.arn

  # 部署包
  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "trails-collector-lambda.zip"

  handler     = "trails_collector_handler.lambda_handler"
  runtime     = var.lambda_runtime
  timeout     = 900  # 15分钟 (雪道采集需要更长时间)
  memory_size = 2048 # 2GB 内存

  # 已移出 VPC：数据库在 Supabase（公网 + TLS），不再需要 NAT Gateway。
  # AWS provider 4.x 删掉 vpc_config 块不会真的解绑，必须显式给空列表。
  vpc_config {
    subnet_ids         = []
    security_group_ids = []
  }

  # 环境变量
  environment {
    variables = {
      # 不设 REDIS_* = 不走缓存（ElastiCache 已下线）
      DATABASE_URL = var.database_url
      ENVIRONMENT  = var.environment
    }
  }

  tags = {
    Name        = "${var.project_name}-trails-collector"
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.trails_collector_lambda
  ]
}

# CloudWatch 日志组
resource "aws_cloudwatch_log_group" "trails_collector_lambda" {
  name              = "/aws/lambda/${var.project_name}-trails-collector"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-trails-collector-logs"
    Environment = var.environment
  }
}

# 输出
output "trails_collector_function_name" {
  description = "Trail Collector Lambda 函数名称"
  value       = aws_lambda_function.trails_collector.function_name
}

output "trails_collector_function_arn" {
  description = "Trail Collector Lambda 函数 ARN"
  value       = aws_lambda_function.trails_collector.arn
}

