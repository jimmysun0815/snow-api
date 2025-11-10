#!/bin/bash
# 打包 Trail Collector Lambda 部署包

set -e

echo "=================================="
echo "🏔️  Trail Collector Lambda 打包工具"
echo "=================================="
echo ""

# 清理旧的打包
echo "🧹 清理旧文件..."
rm -rf trails_lambda_package
rm -f trails-collector-lambda.zip

# 创建打包目录
echo "📦 创建打包目录..."
mkdir -p trails_lambda_package

# 复制必要的 Python 文件
echo "📄 复制 Python 文件..."
cp trails_collector_handler.py trails_lambda_package/
cp collect_trails.py trails_lambda_package/
cp db_manager.py trails_lambda_package/
cp models.py trails_lambda_package/
cp config.py trails_lambda_package/
cp resorts_config.json trails_lambda_package/

# 复制 collectors 目录
echo "📁 复制 collectors 模块..."
cp -r collectors trails_lambda_package/

# 安装依赖到打包目录
echo "📦 安装 Python 依赖..."
pip install -r requirements.txt -t trails_lambda_package/ --quiet

# 进入打包目录并创建 ZIP
echo "🗜️  创建 ZIP 文件..."
cd trails_lambda_package
zip -r ../trails-collector-lambda.zip . -q
cd ..

# 获取文件大小
SIZE=$(du -h trails-collector-lambda.zip | cut -f1)
echo ""
echo "=================================="
echo "✅ 打包完成!"
echo "=================================="
echo ""
echo "📦 文件: trails-collector-lambda.zip"
echo "📊 大小: $SIZE"
echo ""
echo "🚀 部署命令:"
echo ""
echo "# 1. 上传到现有的 Lambda 函数:"
echo "aws lambda update-function-code \\"
echo "  --function-name resort-data-trails-collector \\"
echo "  --zip-file fileb://trails-collector-lambda.zip \\"
echo "  --profile pp"
echo ""
echo "# 2. 或创建新的 Lambda 函数 (参考下面的 Terraform 配置)"
echo ""
echo "# 3. 手动触发:"
echo "aws lambda invoke \\"
echo "  --function-name resort-data-trails-collector \\"
echo "  --payload '{\"limit\": 5}' \\"
echo "  --profile pp \\"
echo "  response.json"
echo ""
echo "=================================="

