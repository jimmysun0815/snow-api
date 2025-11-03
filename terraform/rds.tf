# RDS 子网组
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name        = "${var.project_name}-db-subnet-group"
    Environment = var.environment
  }
}

# RDS PostgreSQL 实例
resource "aws_db_instance" "postgresql" {
  identifier = "${var.project_name}-postgres"

  # 引擎配置
  engine         = "postgres"
  engine_version = "15.12"
  instance_class = var.db_instance_class

  # 存储配置
  allocated_storage     = var.db_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  max_allocated_storage = 100  # 自动扩容上限

  # 数据库配置
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  # 网络配置
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # 备份配置
  backup_retention_period = 7
  backup_window           = "03:00-04:00"  # UTC
  maintenance_window      = "mon:04:00-mon:05:00"

  # 性能配置
  multi_az               = false  # 单可用区节省成本
  deletion_protection    = true   # 防止误删
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.project_name}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  # 监控
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  # 参数组
  parameter_group_name = aws_db_parameter_group.postgresql.name

  tags = {
    Name        = "${var.project_name}-postgres"
    Environment = var.environment
  }
}

# RDS 参数组
resource "aws_db_parameter_group" "postgresql" {
  name   = "${var.project_name}-postgres-params"
  family = "postgres15"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # 记录超过1秒的查询
  }

  tags = {
    Name        = "${var.project_name}-postgres-params"
    Environment = var.environment
  }
}

# RDS 监控角色
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.project_name}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-rds-monitoring-role"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

