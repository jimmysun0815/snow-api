#!/bin/bash
set -e

echo "🔧 修复 Reports S3 Bucket 访问权限并上传测试页面"
echo ""

BUCKET="resort-data-reports"

# 1. 上传测试 index.html
echo "📄 创建测试 index.html..."
cat > /tmp/test_index.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪场数据采集报告 - 测试页面</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            background: white;
            padding: 60px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            font-size: 48px;
            margin-bottom: 20px;
            color: #2d3748;
        }
        p {
            font-size: 18px;
            color: #718096;
            margin-bottom: 30px;
        }
        .status {
            display: inline-block;
            padding: 12px 24px;
            background: #48bb78;
            color: white;
            border-radius: 8px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏔️ 雪场数据采集报告系统</h1>
        <p>系统正在配置中...</p>
        <div class="status">✅ CloudFront CDN 工作正常</div>
        <br><br>
        <p style="font-size: 14px; color: #a0aec0;">
            完成首次数据采集后，此页面将显示报告列表
        </p>
    </div>
</body>
</html>
EOF

echo "☁️  上传到 S3..."
aws s3 cp /tmp/test_index.html "s3://${BUCKET}/index.html" \
    --content-type "text/html" \
    --cache-control "max-age=300" \
    --profile pp \
    --region us-west-2

echo ""
echo "📁 检查 S3 内容..."
aws s3 ls "s3://${BUCKET}/" --profile pp --region us-west-2 --recursive

echo ""
echo "✅ 完成！"
echo ""
echo "访问测试:"
echo "  https://monitoring.steponsnow.com"
echo ""
echo "等待 1-2 分钟让 CloudFront 缓存更新"
echo ""

