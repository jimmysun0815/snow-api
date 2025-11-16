# Lambda 执行角色
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-exec-role"

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
    Name        = "${var.project_name}-lambda-exec-role"
    Environment = var.environment
  }
}

# Lambda 基础策略
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda VPC 访问策略
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Lambda S3 访问策略 (用于报告上传)
resource "aws_iam_role_policy" "lambda_s3_reports" {
  name = "${var.project_name}-lambda-s3-reports"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-reports",
          "arn:aws:s3:::${var.project_name}-reports/*"
        ]
      }
    ]
  })
}

# CloudWatch 日志组 (API Lambda)
resource "aws_cloudwatch_log_group" "api_lambda" {
  name              = "/aws/lambda/${var.project_name}-api"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-api-logs"
    Environment = var.environment
  }
}

# CloudWatch 日志组 (Collector Lambda)
resource "aws_cloudwatch_log_group" "collector_lambda" {
  name              = "/aws/lambda/${var.project_name}-collector"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-collector-logs"
    Environment = var.environment
  }
}

# CloudWatch 日志组 (Contact Info Collector Lambda)
resource "aws_cloudwatch_log_group" "contact_collector_lambda" {
  name              = "/aws/lambda/${var.project_name}-contact-collector"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-contact-collector-logs"
    Environment = var.environment
  }
}

# Lambda 函数 - API
resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"
  role          = aws_iam_role.lambda_exec.arn

  # 部署包 (由 GitHub Actions 构建和上传)
  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "api-lambda.zip"

  handler = "lambda_handler.lambda_handler"
  runtime = var.lambda_runtime
  timeout = var.lambda_timeout
  memory_size = var.lambda_memory

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
      CACHE_TTL         = "300"
      ENVIRONMENT       = var.environment
    }
  }

  tags = {
    Name        = "${var.project_name}-api"
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.api_lambda,
    aws_db_instance.postgresql,
    aws_elasticache_cluster.redis
  ]
}

# Lambda 函数 - 数据采集
resource "aws_lambda_function" "collector" {
  function_name = "${var.project_name}-collector"
  role          = aws_iam_role.lambda_exec.arn

  # 部署包
  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "collector-lambda.zip"

  handler = "collector_handler.lambda_handler"
  runtime = var.lambda_runtime
  timeout = 900  # 15分钟 (数据采集需要更长时间)
  memory_size = 1024

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
    Name        = "${var.project_name}-collector"
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.collector_lambda,
    aws_db_instance.postgresql,
    aws_elasticache_cluster.redis
  ]
}

# Lambda 函数 - 联系信息采集
resource "aws_lambda_function" "contact_collector" {
  function_name = "${var.project_name}-contact-collector"
  role          = aws_iam_role.lambda_exec.arn

  # 部署包 (使用占位符，实际代码由 GitHub Actions 部署)
  filename      = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  handler = "contact_collector_handler.lambda_handler"
  runtime = var.lambda_runtime
  timeout = 900  # 15分钟 (联系信息采集需要较长时间)
  memory_size = 1024

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
    Name        = "${var.project_name}-contact-collector"
    Environment = var.environment
  }

  depends_on = [
    aws_cloudwatch_log_group.contact_collector_lambda,
    aws_db_instance.postgresql,
    aws_elasticache_cluster.redis
  ]
}

# S3 Bucket for Lambda artifacts
resource "aws_s3_bucket" "lambda_artifacts" {
  bucket = "${var.project_name}-lambda-artifacts-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "${var.project_name}-lambda-artifacts"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

