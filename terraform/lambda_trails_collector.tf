# Lambda 函数 - Trail Collector (雪道数据采集)
resource "aws_lambda_function" "trails_collector" {
  function_name = "${var.project_name}-trails-collector"
  role          = aws_iam_role.lambda_exec.arn

  # 部署包
  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "trails-collector-lambda.zip"

  handler = "trails_collector_handler.lambda_handler"
  runtime = var.lambda_runtime
  timeout = 900  # 15分钟 (雪道采集需要更长时间)
  memory_size = 2048  # 2GB 内存

  # VPC 配置
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  # 环境变量
  environment {
    variables = {
      POSTGRES_HOST     = aws_db_instance.postgresql.address
      POSTGRES_PORT     = "5432"
      POSTGRES_USER     = var.db_username
      POSTGRES_PASSWORD = var.db_password
      POSTGRES_DB       = var.db_name
      REDIS_HOST        = aws_elasticache_cluster.redis.cache_nodes[0].address
      REDIS_PORT        = "6379"
      REDIS_DB          = "0"
      ENVIRONMENT       = var.environment
    }
  }

  tags = {
    Name        = "${var.project_name}-trails-collector"
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.trails_collector_lambda,
    aws_db_instance.postgresql,
    aws_elasticache_cluster.redis
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

