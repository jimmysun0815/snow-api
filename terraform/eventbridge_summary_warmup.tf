# 定时预热 /api/resorts/summary：每 5 分钟请求一次，保持 API Lambda 实例活跃 + Redis 缓存有效

data "archive_file" "warmup_summary" {
  type        = "zip"
  source_file = "${path.module}/../warmup_summary_handler.py"
  output_path = "${path.module}/warmup_summary_lambda.zip"
}

# 预热 Lambda 使用基础执行角色（仅打公网 API，不需要 VPC）
resource "aws_iam_role" "warmup_summary" {
  name = "${var.project_name}-warmup-summary-role"

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
    Name        = "${var.project_name}-warmup-summary-role"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "warmup_summary_basic" {
  role       = aws_iam_role.warmup_summary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "warmup_summary" {
  name              = "/aws/lambda/${var.project_name}-warmup-summary"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-warmup-summary-logs"
    Environment = var.environment
  }
}

resource "aws_lambda_function" "warmup_summary" {
  function_name = "${var.project_name}-warmup-summary"
  role          = aws_iam_role.warmup_summary.arn
  handler       = "warmup_summary_handler.lambda_handler"
  runtime       = "python3.10"
  timeout       = 90
  memory_size   = 128

  filename         = data.archive_file.warmup_summary.output_path
  source_code_hash = data.archive_file.warmup_summary.output_base64sha256

  environment {
    variables = {
      API_URL = "https://api.${var.domain_name}"
    }
  }

  tags = {
    Name        = "${var.project_name}-warmup-summary"
    Environment = var.environment
  }

  depends_on = [aws_cloudwatch_log_group.warmup_summary]
}

# EventBridge 规则：每 5 分钟预热一次，保持主 API Lambda 实例活跃
resource "aws_cloudwatch_event_rule" "summary_warmup" {
  name                = "${var.project_name}-summary-warmup"
  description         = "Warm up /api/resorts/summary every 5 minutes to reduce cold starts"
  schedule_expression = "rate(5 minutes)"

  tags = {
    Name        = "${var.project_name}-summary-warmup"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "warmup_summary_lambda" {
  rule      = aws_cloudwatch_event_rule.summary_warmup.name
  target_id = "WarmupSummaryLambda"
  arn       = aws_lambda_function.warmup_summary.arn
}

resource "aws_lambda_permission" "eventbridge_warmup_summary" {
  statement_id  = "AllowEventBridgeWarmupSummary"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.warmup_summary.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.summary_warmup.arn
}
