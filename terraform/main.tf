terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.67"
    }
  }
  
  # 使用本地 Backend（状态文件保存在本地）
  # 如果需要团队协作，可以切换到 S3 backend
  # backend "s3" {
  #   bucket  = "resort-data-terraform-state"
  #   key     = "terraform.tfstate"
  #   region  = "us-west-2"
  #   profile = "pp"
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = "pp"  # AWS CLI profile 名称
}

# 获取当前账户信息
data "aws_caller_identity" "current" {}

# 获取可用区
data "aws_availability_zones" "available" {
  state = "available"
}

