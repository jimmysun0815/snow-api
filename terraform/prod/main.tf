# =====================================================
# Prod 环境 - 通知系统 Lambda
# =====================================================
# 说明：
# - 只部署通知相关的 Lambda (sqs-notification-processor)
# - 使用 Dev 环境相同的 VPC
# - 独立的 Supabase 配置（Prod 环境）
# =====================================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.67"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile != "" ? var.aws_profile : null
}

# =====================================================
# 数据源：引用已有资源
# =====================================================

# S3 Bucket (Lambda 代码存放)
data "aws_s3_bucket" "lambda_artifacts" {
  bucket = "resort-data-lambda-artifacts-579866932024"
}

# IAM Role (Lambda 执行角色)
data "aws_iam_role" "lambda_exec" {
  name = "resort-data-sqs-lambda-exec-role"  # Dev 环境的 Lambda 执行角色
}

# =====================================================
# Prod 环境 Lambda: SQS Notification Processor
# =====================================================

resource "aws_lambda_function" "prod_sqs_notification_processor" {
  function_name = "${var.project_name}-prod-notification-processor"
  role          = data.aws_iam_role.lambda_exec.arn
  handler       = "sqs_notification_processor.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = 60
  memory_size   = 512
  
  # 限制并发
  reserved_concurrent_executions = 10

  s3_bucket = data.aws_s3_bucket.lambda_artifacts.id
  s3_key    = "sqs-notification-processor.zip"

  environment {
    variables = {
      # Supabase 配置 (Prod 环境)
      SUPABASE_URL         = var.prod_supabase_url
      SUPABASE_SERVICE_KEY = var.prod_supabase_service_key
      
      # Firebase 配置 (Dev 和 Prod 共用)
      FIREBASE_PROJECT_ID     = var.firebase_project_id
      FIREBASE_PRIVATE_KEY_ID = var.firebase_private_key_id
      FIREBASE_PRIVATE_KEY    = var.firebase_private_key
      FIREBASE_CLIENT_EMAIL   = var.firebase_client_email
      FIREBASE_CLIENT_ID      = var.firebase_client_id
      
      # 配置
      BATCH_SIZE = "10"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.prod_notification_processor
  ]

  tags = {
    Name        = "${var.project_name}-prod-notification-processor"
    Environment = "prod"
    Purpose     = "Process notifications for Prod Supabase"
  }
}

# =====================================================
# CloudWatch 日志组
# =====================================================

resource "aws_cloudwatch_log_group" "prod_notification_processor" {
  name              = "/aws/lambda/${var.project_name}-prod-notification-processor"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-prod-notification-processor-logs"
    Environment = "prod"
  }
}

# =====================================================
# Lambda Function URL (用于 Supabase Webhook)
# =====================================================

resource "aws_lambda_function_url" "prod_notification_processor" {
  function_name      = aws_lambda_function.prod_sqs_notification_processor.function_name
  authorization_type = "NONE"  # 公开访问（Supabase Webhook 需要）

  cors {
    allow_origins     = ["*"]
    allow_methods     = ["POST"]
    allow_headers     = ["*"]
    max_age          = 86400
  }
}

# =====================================================
# Outputs
# =====================================================

output "lambda_function_name" {
  description = "Prod Notification Lambda function name"
  value       = aws_lambda_function.prod_sqs_notification_processor.function_name
}

output "lambda_function_arn" {
  description = "Prod Notification Lambda function ARN"
  value       = aws_lambda_function.prod_sqs_notification_processor.arn
}

output "lambda_function_url" {
  description = "Prod Notification Lambda Function URL (用于 Supabase Webhook)"
  value       = aws_lambda_function_url.prod_notification_processor.function_url
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.prod_notification_processor.name
}

