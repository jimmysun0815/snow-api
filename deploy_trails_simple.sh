#!/bin/bash
# 简化的 Trail Collector 部署和触发脚本

set -e

FUNCTION_NAME="resort-data-trails-collector"
S3_BUCKET="resort-data-lambda-artifacts-579866932024"
ZIP_FILE="trails-collector-lambda.zip"
AWS_PROFILE="pp"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       🏔️  Trail Collector - 简化部署和触发流程                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 步骤 1: 打包
echo "📦 步骤 1/4: 打包 Lambda..."
echo "----------------------------------------"

# 清理
rm -rf trails_lambda_package
rm -f $ZIP_FILE

# 创建打包目录
mkdir -p trails_lambda_package

# 复制文件
echo "   ├─ 复制 Python 文件..."
cp trails_collector_handler.py trails_lambda_package/
cp collect_trails.py trails_lambda_package/
cp db_manager.py trails_lambda_package/
cp models.py trails_lambda_package/
cp config.py trails_lambda_package/
cp resorts_config.json trails_lambda_package/
cp trails_report_html.py trails_lambda_package/

echo "   ├─ 复制 collectors 模块..."
cp -r collectors trails_lambda_package/

echo "   ├─ 安装依赖 (这可能需要几分钟)..."

# 使用 Docker 来打包 Lambda 兼容的依赖
if command -v docker &> /dev/null; then
    echo "   ├─ 使用 Docker (Amazon Linux 2) 打包依赖..."
    
    # 创建临时 Dockerfile
    cat > Dockerfile.lambda << 'DOCKERFILE'
FROM amazonlinux:2

RUN yum install -y python3 python3-pip gcc python3-devel postgresql-devel zip && \
    yum clean all

WORKDIR /build

COPY trails_lambda_package/requirements_temp.txt /build/requirements.txt

RUN pip3 install -r requirements.txt -t /build/python/ && \
    cd /build && \
    rm -rf python/*.dist-info python/__pycache__

CMD ["bash"]
DOCKERFILE

    # 创建临时 requirements
    cat > trails_lambda_package/requirements_temp.txt << EOF
requests>=2.31.0
beautifulsoup4>=4.12.0
html5lib>=1.1
psycopg2-binary>=2.9.9
sqlalchemy>=2.0.23
redis>=5.0.1
async-timeout>=4.0.0
python-dotenv>=1.0.0
firebase-admin>=6.2.0
typing-extensions>=4.0.0
EOF

    # 构建并运行容器来安装依赖
    docker build -f Dockerfile.lambda -t lambda-builder:temp . --quiet
    docker run --rm -v "$PWD/trails_lambda_package":/output lambda-builder:temp \
        bash -c "cp -r /build/python/* /output/"
    
    # 清理
    rm Dockerfile.lambda
    rm trails_lambda_package/requirements_temp.txt
    docker rmi lambda-builder:temp --force 2>/dev/null
    
    echo "   ├─ Docker 打包完成"
else
    echo "   ⚠️  未找到 Docker，尝试使用本地 pip..."
    pip3 install --upgrade \
        requests beautifulsoup4 html5lib sqlalchemy redis async-timeout \
        python-dotenv firebase-admin typing-extensions psycopg2-binary \
        -t trails_lambda_package/ --quiet
fi

echo "   └─ 创建 ZIP 文件..."
cd trails_lambda_package
zip -r ../$ZIP_FILE . -q
cd ..

SIZE=$(du -h $ZIP_FILE | cut -f1)
echo "   ✅ 打包完成! 文件大小: $SIZE"
echo ""

# 步骤 2: 上传到 S3
echo "☁️  步骤 2/4: 上传到 S3..."
echo "----------------------------------------"
aws s3 cp $ZIP_FILE s3://$S3_BUCKET/$ZIP_FILE --profile $AWS_PROFILE
echo "   ✅ 上传完成!"
echo ""

# 步骤 3: 检查 Lambda 是否存在，如果不存在则创建
echo "🔍 步骤 3/4: 检查/创建 Lambda 函数..."
echo "----------------------------------------"

if aws lambda get-function --function-name $FUNCTION_NAME --profile $AWS_PROFILE &>/dev/null; then
    echo "   Lambda 函数已存在，更新代码..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --s3-bucket $S3_BUCKET \
        --s3-key $ZIP_FILE \
        --profile $AWS_PROFILE \
        --output json | jq -r '"   ✅ 更新完成! LastModified: \(.LastModified)"'
else
    echo "   ⚠️  Lambda 函数不存在!"
    echo "   请先使用 Terraform 创建 Lambda 函数:"
    echo ""
    echo "   cd terraform"
    echo "   terraform apply -target=aws_lambda_function.trails_collector"
    echo ""
    exit 1
fi

echo ""

# 步骤 4: 触发 Lambda
echo "🚀 步骤 4/4: 触发 Lambda 采集雪道数据..."
echo "----------------------------------------"
echo ""
echo "请选择运行模式:"
echo "  1) 测试模式 (采集 5 个雪场)"
echo "  2) 批量模式 (采集 50 个雪场)"
echo "  3) 全量模式 (采集所有雪场 - 约 309 个)"
echo "  4) 跳过触发"
echo ""
read -p "请输入选项 (1-4): " choice

case $choice in
    1)
        echo ""
        echo "▶️  测试模式: 采集 5 个雪场..."
        aws lambda invoke \
            --function-name $FUNCTION_NAME \
            --cli-binary-format raw-in-base64-out \
            --payload '{"limit": 5}' \
            --profile $AWS_PROFILE \
            --log-type Tail \
            response.json | jq -r '.LogResult' | base64 -d
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Lambda 响应:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        cat response.json
        echo ""
        ;;
    2)
        echo ""
        echo "▶️  批量模式: 采集 50 个雪场..."
        aws lambda invoke \
            --function-name $FUNCTION_NAME \
            --cli-binary-format raw-in-base64-out \
            --payload '{"limit": 50}' \
            --profile $AWS_PROFILE \
            --log-type Tail \
            response.json | jq -r '.LogResult' | base64 -d
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Lambda 响应:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        cat response.json
        echo ""
        ;;
    3)
        echo ""
        echo "⚠️  全量模式会采集所有 309 个雪场，可能需要很长时间!"
        read -p "确定继续? (y/N): " confirm
        if [ "$confirm" = "y" ]; then
            echo ""
            echo "▶️  全量模式: 采集所有雪场..."
            aws lambda invoke \
                --function-name $FUNCTION_NAME \
                --cli-binary-format raw-in-base64-out \
                --payload '{}' \
                --profile $AWS_PROFILE \
                --log-type Tail \
                response.json | jq -r '.LogResult' | base64 -d
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Lambda 响应:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            cat response.json
            echo ""
        else
            echo "已取消"
        fi
        ;;
    4)
        echo ""
        echo "⏭️  跳过触发"
        echo ""
        echo "你可以稍后手动触发:"
        echo "aws lambda invoke \\"
        echo "  --function-name $FUNCTION_NAME \\"
        echo "  --cli-binary-format raw-in-base64-out \\"
        echo "  --payload '{\"limit\": 50}' \\"
        echo "  --profile $AWS_PROFILE \\"
        echo "  --log-type Tail \\"
        echo "  response.json"
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                          ✅ 完成!                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "查看 Lambda 日志:"
echo "aws logs tail /aws/lambda/$FUNCTION_NAME --follow --profile $AWS_PROFILE"
echo ""

