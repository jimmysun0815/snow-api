# Lambda Functions for Push Notifications

# 1. Notification Handler Lambda (处理通知队列)
resource "aws_lambda_function" "notification_handler" {
  function_name = "${var.project_name}-notification-handler"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "notification_handler.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = 60
  memory_size   = 512

  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "notification-handler.zip"

  environment {
    variables = {
      DB_HOST     = aws_db_instance.postgresql.address
      DB_NAME     = var.db_name
      DB_USER     = var.db_username
      DB_PASSWORD = var.db_password
      REDIS_HOST  = aws_elasticache_cluster.redis.cache_nodes[0].address
      REDIS_PORT  = aws_elasticache_cluster.redis.cache_nodes[0].port
      
      # Firebase 配置
      FIREBASE_PROJECT_ID     = var.firebase_project_id
      FIREBASE_PRIVATE_KEY_ID = var.firebase_private_key_id
      FIREBASE_PRIVATE_KEY    = var.firebase_private_key
      FIREBASE_CLIENT_EMAIL   = var.firebase_client_email
      FIREBASE_CLIENT_ID      = var.firebase_client_id
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_cloudwatch_log_group.notification_handler
  ]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "notification_handler" {
  name              = "/aws/lambda/${var.project_name}-notification-handler"
  retention_in_days = 7
}

# EventBridge 规则：每分钟运行一次
# ⚠️ 已禁用 - 现在使用 Supabase Webhook + Lambda Function URL 实时推送
# resource "aws_cloudwatch_event_rule" "notification_handler_schedule" {
#   name                = "${var.project_name}-notification-handler-schedule"
#   description         = "Trigger notification handler every minute"
#   schedule_expression = "rate(1 minute)"
# }

# resource "aws_cloudwatch_event_target" "notification_handler" {
#   rule      = aws_cloudwatch_event_rule.notification_handler_schedule.name
#   target_id = "NotificationHandler"
#   arn       = aws_lambda_function.notification_handler.arn
# }

# resource "aws_lambda_permission" "allow_eventbridge_notification" {
#   statement_id  = "AllowExecutionFromEventBridge"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.notification_handler.function_name
#   principal     = "events.amazonaws.com"
#   source_arn    = aws_cloudwatch_event_rule.notification_handler_schedule.arn
# }

# 2. Snow Checker Lambda (降雪检查和推送)
resource "aws_lambda_function" "snow_checker" {
  function_name = "${var.project_name}-snow-checker"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "check_snow_and_notify.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = 300
  memory_size   = 1024

  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "snow-checker.zip"

  environment {
    variables = {
      DB_HOST     = aws_db_instance.postgresql.address
      DB_NAME     = var.db_name
      DB_USER     = var.db_username
      DB_PASSWORD = var.db_password
      REDIS_HOST  = aws_elasticache_cluster.redis.cache_nodes[0].address
      REDIS_PORT  = aws_elasticache_cluster.redis.cache_nodes[0].port
      
      # Firebase 配置
      FIREBASE_PROJECT_ID     = var.firebase_project_id
      FIREBASE_PRIVATE_KEY_ID = var.firebase_private_key_id
      FIREBASE_PRIVATE_KEY    = var.firebase_private_key
      FIREBASE_CLIENT_EMAIL   = var.firebase_client_email
      FIREBASE_CLIENT_ID      = var.firebase_client_id
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_cloudwatch_log_group.snow_checker
  ]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "snow_checker" {
  name              = "/aws/lambda/${var.project_name}-snow-checker"
  retention_in_days = 7
}

# EventBridge 规则：每小时运行一次
resource "aws_cloudwatch_event_rule" "snow_checker_schedule" {
  name                = "${var.project_name}-snow-checker-schedule"
  description         = "Check for snow alerts every hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "snow_checker" {
  rule      = aws_cloudwatch_event_rule.snow_checker_schedule.name
  target_id = "SnowChecker"
  arn       = aws_lambda_function.snow_checker.arn
}

resource "aws_lambda_permission" "allow_eventbridge_snow" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.snow_checker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.snow_checker_schedule.arn
}

# Outputs
output "notification_handler_function_name" {
  description = "Notification Handler Lambda function name"
  value       = aws_lambda_function.notification_handler.function_name
}

output "snow_checker_function_name" {
  description = "Snow Checker Lambda function name"
  value       = aws_lambda_function.snow_checker.function_name
}

