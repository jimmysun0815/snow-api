#!/bin/bash
# 超级简化版 - 打包上传 Lambda

set -e

FUNCTION_NAME="resort-data-trails-collector"
S3_BUCKET="resort-data-lambda-artifacts-579866932024"
ZIP_FILE="trails-lambda.zip"
AWS_PROFILE="pp"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       🏔️  Trail Collector - 超简化部署                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. 打包
echo "📦 步骤 1/3: 打包..."
rm -rf package $ZIP_FILE

# 创建打包目录
mkdir -p package

# 复制核心文件
echo "   ├─ 复制文件..."
cp trails_collector_handler.py package/
cp collect_trails.py package/
cp db_manager.py package/
cp models.py package/
cp config.py package/
cp resorts_config.json package/
cp trails_report_html.py package/
cp -r collectors package/

# 安装依赖 - 使用 Docker 和 Amazon Linux 2
echo "   ├─ 安装依赖 (使用 Docker + Amazon Linux 2)..."
docker run --rm \
    -v "$PWD":/var/task \
    public.ecr.aws/sam/build-python3.11:latest \
    bash -c "pip install -r /var/task/requirements.txt -t /var/task/package/ --quiet"

# 打包
echo "   └─ 创建 ZIP..."
cd package
zip -r ../$ZIP_FILE . -q
cd ..
rm -rf package

SIZE=$(du -h $ZIP_FILE | cut -f1)
echo "   ✅ 打包完成! 大小: $SIZE"
echo ""

# 2. 上传到 S3
echo "☁️  步骤 2/3: 上传到 S3..."
aws s3 cp $ZIP_FILE s3://$S3_BUCKET/$ZIP_FILE --profile $AWS_PROFILE
echo "   ✅ 上传完成!"
echo ""

# 3. 更新 Lambda
echo "🔄 步骤 3/3: 更新 Lambda..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --s3-bucket $S3_BUCKET \
    --s3-key $ZIP_FILE \
    --profile $AWS_PROFILE \
    --output json | jq -r '"   ✅ 更新完成! LastModified: \(.LastModified)"'

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                          ✅ 部署完成!                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 触发 Lambda:"
echo ""
echo "# 测试 (5 个雪场):"
echo "aws lambda invoke --function-name $FUNCTION_NAME --cli-binary-format raw-in-base64-out --payload '{\"limit\": 5}' --profile $AWS_PROFILE --log-type Tail response.json | jq -r '.LogResult' | base64 -d"
echo ""
echo "# 批量 (50 个雪场):"
echo "aws lambda invoke --function-name $FUNCTION_NAME --cli-binary-format raw-in-base64-out --payload '{\"limit\": 50}' --profile $AWS_PROFILE --log-type Tail response.json | jq -r '.LogResult' | base64 -d"
echo ""
echo "# 全部 (309 个雪场):"
echo "aws lambda invoke --function-name $FUNCTION_NAME --cli-binary-format raw-in-base64-out --payload '{}' --profile $AWS_PROFILE --log-type Tail response.json | jq -r '.LogResult' | base64 -d"
echo ""

