#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📦 部署数据库迁移 Lambda"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$(dirname "$0")"

# 1. 准备部署包
echo "🔨 准备部署包..."
rm -rf migration_package
mkdir -p migration_package

# 2. 使用 Docker 安装 Lambda 兼容的依赖
echo "📦 安装 psycopg2-binary (Lambda 兼容版本)..."
docker run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  public.ecr.aws/sam/build-python3.11:latest \
  bash -c "pip install psycopg2-binary -t migration_package/"

# 3. 复制迁移脚本
echo "📄 复制迁移脚本..."
cp migrate_add_contact_info.py migration_package/

# 4. 打包
echo "📦 打包..."
cd migration_package
zip -r ../migration.zip . > /dev/null
cd ..

# 5. 上传到 S3
echo "☁️  上传到 S3..."
BUCKET=$(cd terraform && terraform output -raw lambda_artifacts_bucket)
aws s3 cp migration.zip "s3://${BUCKET}/migration.zip" --profile pp

# 6. 更新 collector Lambda 的代码（临时用于执行迁移）
echo "🔄 临时更新 collector Lambda..."
FUNCTION_NAME=$(cd terraform && terraform output -raw lambda_collector_function_name)
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --s3-bucket "$BUCKET" \
  --s3-key "migration.zip" \
  --profile pp > /dev/null

echo "⏳ 等待 Lambda 更新完成..."
aws lambda wait function-updated \
  --function-name "$FUNCTION_NAME" \
  --profile pp

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 执行数据库迁移"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 7. 执行迁移
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --log-type Tail \
  --profile pp \
  migration_response.json \
  | jq -r '.LogResult' | base64 -d

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📄 迁移响应:"
cat migration_response.json | jq .
echo ""

# 8. 恢复原始 Lambda 代码
echo "🔄 恢复原始 Lambda 代码..."
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --s3-bucket "$BUCKET" \
  --s3-key "lambda.zip" \
  --profile pp > /dev/null

echo "⏳ 等待 Lambda 恢复完成..."
aws lambda wait function-updated \
  --function-name "$FUNCTION_NAME" \
  --profile pp

# 9. 清理
echo "🧹 清理临时文件..."
rm -rf migration_package migration.zip migration_response.json

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                          ✅ 完成!                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "下一步: 重新采集数据以获取联系信息"
echo "  make update-data"
echo ""

