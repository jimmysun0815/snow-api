# =====================================================
# SQS + Lambda 实时推送通知架构
# 架构: 数据库触发器 → Edge Function → SQS → Lambda → Firebase → 设备
# =====================================================
# 注意: 所有变量已在 variables.tf 中定义

# =====================================================
# 1. SQS 队列（接收推送通知请求）
# =====================================================

resource "aws_sqs_queue" "push_notification_queue" {
  name                       = "${var.project_name}-push-notifications"
  delay_seconds              = 0                    # 立即可用
  max_message_size           = 262144               # 256 KB
  message_retention_seconds  = 345600               # 4 天
  receive_wait_time_seconds  = 20                   # 长轮询，减少空请求
  visibility_timeout_seconds = 180                  # 3 分钟（Lambda 超时的3倍）

  # 死信队列配置
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.push_notification_dlq.arn
    maxReceiveCount     = 3                         # 失败3次后进入死信队列
  })

  tags = {
    Name        = "${var.project_name}-push-notifications"
    Environment = var.environment
    Purpose     = "Real-time push notification queue"
  }
}

# =====================================================
# 2. 死信队列（处理失败的消息）
# =====================================================

resource "aws_sqs_queue" "push_notification_dlq" {
  name                       = "${var.project_name}-push-notifications-dlq"
  message_retention_seconds  = 1209600              # 14 天
  receive_wait_time_seconds  = 0

  tags = {
    Name        = "${var.project_name}-push-notifications-dlq"
    Environment = var.environment
    Purpose     = "Dead letter queue for failed notifications"
  }
}

# =====================================================
# 3. CloudWatch 告警（监控死信队列）
# =====================================================

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.project_name}-push-notification-dlq-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300                         # 5 分钟
  statistic           = "Average"
  threshold           = 0                           # 有任何消息就告警
  alarm_description   = "Alert when messages appear in DLQ"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.push_notification_dlq.name
  }

  # 可选：配置 SNS 发送告警邮件
  # alarm_actions = [aws_sns_topic.alerts.arn]
}

# =====================================================
# 4. Lambda 函数（处理 SQS 消息）
# =====================================================

resource "aws_lambda_function" "sqs_notification_processor" {
  function_name = "${var.project_name}-sqs-notification-processor"
  role          = aws_iam_role.sqs_lambda_exec.arn
  handler       = "sqs_notification_processor.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = 60                                # 1 分钟超时
  memory_size   = 512
  
  # 限制并发，避免 Firebase 过载
  reserved_concurrent_executions = 10

  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "sqs-notification-processor.zip"

  environment {
    variables = {
      # Supabase 配置
      SUPABASE_URL         = var.supabase_url
      SUPABASE_SERVICE_KEY = var.supabase_service_key
      
      # Firebase 配置
      FIREBASE_PROJECT_ID     = var.firebase_project_id
      FIREBASE_PRIVATE_KEY_ID = var.firebase_private_key_id
      FIREBASE_PRIVATE_KEY    = var.firebase_private_key
      FIREBASE_CLIENT_EMAIL   = var.firebase_client_email
      FIREBASE_CLIENT_ID      = var.firebase_client_id
      
      # 配置
      BATCH_SIZE = "10"                             # 每次处理10条消息
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.sqs_notification_processor
  ]

  tags = {
    Name        = "${var.project_name}-sqs-notification-processor"
    Environment = var.environment
    Purpose     = "Process SQS messages and send to Firebase"
  }
}

# =====================================================
# 5. CloudWatch 日志组
# =====================================================

resource "aws_cloudwatch_log_group" "sqs_notification_processor" {
  name              = "/aws/lambda/${var.project_name}-sqs-notification-processor"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-sqs-notification-processor-logs"
    Environment = var.environment
  }
}

# =====================================================
# 6. Lambda 事件源映射（SQS → Lambda）
# =====================================================

resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.push_notification_queue.arn
  function_name    = aws_lambda_function.sqs_notification_processor.arn
  
  # 批处理配置
  batch_size                         = 10           # 每次处理10条消息
  maximum_batching_window_in_seconds = 5            # 最多等待5秒凑够批次
  
  # 错误处理
  function_response_types = ["ReportBatchItemFailures"]  # 支持部分失败
  
  # 并发控制
  scaling_config {
    maximum_concurrency = 10                        # 最多10个并发实例
  }

  enabled = true
}

# =====================================================
# 7. IAM 角色（Lambda 执行角色）
# =====================================================

resource "aws_iam_role" "sqs_lambda_exec" {
  name = "${var.project_name}-sqs-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-sqs-lambda-exec-role"
    Environment = var.environment
  }
}

# =====================================================
# 8. IAM 策略（Lambda 权限）
# =====================================================

resource "aws_iam_role_policy" "sqs_lambda_policy" {
  name = "${var.project_name}-sqs-lambda-policy"
  role = aws_iam_role.sqs_lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # SQS 读取权限
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.push_notification_queue.arn
      },
      # CloudWatch Logs 写入权限
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# =====================================================
# 9. IAM 用户（供 Supabase Edge Function 使用）
# =====================================================

resource "aws_iam_user" "supabase_sqs_user" {
  name = "${var.project_name}-supabase-sqs-user"

  tags = {
    Name        = "${var.project_name}-supabase-sqs-user"
    Environment = var.environment
    Purpose     = "Supabase Edge Function to send SQS messages"
  }
}

# =====================================================
# 10. IAM 用户策略（只允许发送消息到 SQS）
# =====================================================

resource "aws_iam_user_policy" "supabase_sqs_user_policy" {
  name = "${var.project_name}-supabase-sqs-send-policy"
  user = aws_iam_user.supabase_sqs_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.push_notification_queue.arn
      }
    ]
  })
}

# =====================================================
# 11. 生成访问密钥（供 Supabase 使用）
# =====================================================

resource "aws_iam_access_key" "supabase_sqs_user_key" {
  user = aws_iam_user.supabase_sqs_user.name
}

# =====================================================
# Outputs
# =====================================================

output "sqs_queue_url" {
  description = "SQS Queue URL for push notifications"
  value       = aws_sqs_queue.push_notification_queue.url
}

output "sqs_queue_arn" {
  description = "SQS Queue ARN"
  value       = aws_sqs_queue.push_notification_queue.arn
}

output "sqs_dlq_url" {
  description = "Dead Letter Queue URL"
  value       = aws_sqs_queue.push_notification_dlq.url
}

output "lambda_function_name" {
  description = "Lambda function name for SQS processor"
  value       = aws_lambda_function.sqs_notification_processor.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.sqs_notification_processor.arn
}

output "supabase_aws_access_key_id" {
  description = "AWS Access Key ID for Supabase (store in Supabase secrets)"
  value       = aws_iam_access_key.supabase_sqs_user_key.id
  sensitive   = true
}

output "supabase_aws_secret_access_key" {
  description = "AWS Secret Access Key for Supabase (store in Supabase secrets)"
  value       = aws_iam_access_key.supabase_sqs_user_key.secret
  sensitive   = true
}

# =====================================================
# 监控指标（可选，用于 CloudWatch Dashboard）
# =====================================================

resource "aws_cloudwatch_metric_alarm" "sqs_age_alarm" {
  alarm_name          = "${var.project_name}-sqs-message-age-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 300                         # 5分钟
  alarm_description   = "Alert when messages are older than 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.push_notification_queue.name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors_alarm" {
  alarm_name          = "${var.project_name}-lambda-errors-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5                           # 5分钟内超过5个错误
  alarm_description   = "Alert when Lambda has too many errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.sqs_notification_processor.function_name
  }
}
