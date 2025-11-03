# EventBridge 规则 - 定时触发数据采集
resource "aws_cloudwatch_event_rule" "data_collection" {
  name                = "${var.project_name}-data-collection"
  description         = "Trigger data collection Lambda function"
  schedule_expression = var.data_collection_schedule

  tags = {
    Name        = "${var.project_name}-data-collection"
    Environment = var.environment
  }
}

# EventBridge 目标 - Lambda
resource "aws_cloudwatch_event_target" "collector_lambda" {
  rule      = aws_cloudwatch_event_rule.data_collection.name
  target_id = "CollectorLambda"
  arn       = aws_lambda_function.collector.arn
}

# Lambda 权限 - 允许 EventBridge 调用
resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.data_collection.arn
}

