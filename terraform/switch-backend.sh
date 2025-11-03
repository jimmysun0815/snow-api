#!/bin/bash

# 切换 Terraform Backend 配置脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "$1" in
  local)
    echo "🔄 切换到本地 Backend..."
    if [ ! -f "main.tf.s3" ]; then
      cp main.tf main.tf.s3
      echo "✅ 已备份 S3 配置到 main.tf.s3"
    fi
    cp main.tf.local main.tf
    echo "✅ 已切换到本地 Backend"
    echo "⚠️  注意：本地 backend 不适合生产环境！"
    ;;
    
  s3)
    echo "🔄 切换到 S3 Backend..."
    if [ ! -f "main.tf.s3" ]; then
      echo "❌ 未找到 main.tf.s3 备份文件"
      exit 1
    fi
    cp main.tf.s3 main.tf
    echo "✅ 已切换到 S3 Backend"
    ;;
    
  *)
    echo "用法: $0 {local|s3}"
    echo ""
    echo "  local - 切换到本地 Backend（测试用）"
    echo "  s3    - 切换到 S3 Backend（生产用）"
    exit 1
    ;;
esac

echo ""
echo "下一步："
echo "  1. rm -rf .terraform .terraform.lock.hcl"
echo "  2. terraform init"

