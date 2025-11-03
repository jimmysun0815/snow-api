# AWS 区域
variable "aws_region" {
  description = "AWS 区域"
  type        = string
  default     = "us-west-2"
}

# 项目名称
variable "project_name" {
  description = "项目名称"
  type        = string
  default     = "resort-data"
}

# 环境
variable "environment" {
  description = "环境 (dev/staging/prod)"
  type        = string
  default     = "prod"
}

# 数据库配置
variable "db_username" {
  description = "RDS 数据库用户名"
  type        = string
  default     = "app"
  sensitive   = true
}

variable "db_password" {
  description = "RDS 数据库密码"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "数据库名称"
  type        = string
  default     = "snow"
}

# Redis 配置
variable "redis_node_type" {
  description = "Redis 节点类型"
  type        = string
  default     = "cache.t4g.micro"
}

# RDS 配置
variable "db_instance_class" {
  description = "RDS 实例类型"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS 存储大小 (GB)"
  type        = number
  default     = 20
}

# Lambda 配置
variable "lambda_runtime" {
  description = "Lambda 运行时"
  type        = string
  default     = "python3.10"
}

variable "lambda_timeout" {
  description = "Lambda 超时时间 (秒)"
  type        = number
  default     = 30
}

variable "lambda_memory" {
  description = "Lambda 内存 (MB)"
  type        = number
  default     = 512
}

# 数据采集间隔
variable "data_collection_schedule" {
  description = "数据采集 cron 表达式 (UTC)"
  type        = string
  default     = "cron(0 * * * ? *)"  # 每小时
}

# 自定义域名
variable "domain_name" {
  description = "自定义域名 (已在 Route53 托管)"
  type        = string
  default     = "steponsnow.com"
}

