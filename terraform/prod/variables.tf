# =====================================================
# Prod 环境变量配置
# =====================================================

variable "aws_region" {
  description = "AWS 区域"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "项目名称"
  type        = string
  default     = "resort-data"
}

variable "lambda_runtime" {
  description = "Lambda 运行时"
  type        = string
  default     = "python3.10"
}

# =====================================================
# Prod Supabase 配置
# =====================================================

variable "prod_supabase_url" {
  description = "Prod Supabase Project URL"
  type        = string
}

variable "prod_supabase_service_key" {
  description = "Prod Supabase Service Role Key"
  type        = string
  sensitive   = true
}

# =====================================================
# Firebase 配置 (Dev 和 Prod 共用)
# =====================================================

variable "firebase_project_id" {
  description = "Firebase Project ID"
  type        = string
}

variable "firebase_private_key_id" {
  description = "Firebase Private Key ID"
  type        = string
  sensitive   = true
}

variable "firebase_private_key" {
  description = "Firebase Private Key"
  type        = string
  sensitive   = true
}

variable "firebase_client_email" {
  description = "Firebase Client Email"
  type        = string
}

variable "firebase_client_id" {
  description = "Firebase Client ID"
  type        = string
  sensitive   = true
}

# =====================================================
# AWS Profile (可选)
# =====================================================

variable "aws_profile" {
  description = "AWS CLI profile 名称 (本地开发用，CI/CD 留空)"
  type        = string
  default     = ""
}

