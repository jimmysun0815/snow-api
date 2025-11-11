# 📊 采集报告系统使用指南

## 🎯 系统概述

自动生成美观的 HTML 采集报告，并通过 CloudFront CDN 分发，支持：
- ✅ 每次采集自动生成报告
- ✅ 报告列表页面，可搜索筛选
- ✅ 详细的采集统计和失败信息
- ✅ CloudFront 加速访问
- ✅ 自动保存历史报告

##  部署步骤

### 1️⃣ 部署 Terraform 资源

```bash
cd /Users/jimmysun/Desktop/workspace/resort-data/backend-api/terraform

# 部署 S3 + CloudFront
terraform apply
```

这会创建：
- S3 Bucket: `resort-data-reports`
- CloudFront Distribution
- IAM 权限

### 2️⃣ 更新 GitHub Actions

已经自动包含在部署流程中，每次 push 代码会自动部署。

### 3️⃣ 添加环境变量到 Lambda

```bash
# 获取 S3 bucket 名称
REPORTS_BUCKET=$(cd terraform && terraform output -raw reports_s3_bucket)

# 更新 Collector Lambda 环境变量
aws lambda update-function-configuration \
  --function-name resort-data-collector \
  --environment "Variables={REPORTS_BUCKET=$REPORTS_BUCKET}" \
  --profile pp \
  --region us-west-2
```

## 📝 使用方法

### 访问报告列表

获取 CloudFront URL：
```bash
cd terraform
terraform output reports_cloudfront_url
```

访问: `https://xxxxxx.cloudfront.net/`

### 报告结构

```
S3 Bucket (resort-data-reports)
├── index.html                                    # 报告列表页面
└── reports/
    ├── latest.html                               # 最新报告（快捷访问）
    ├── report_20251110_120000.html              # 历史报告
    ├── report_20251110_150000.html
    └── report_20251110_180000.html
```

### CloudFront URL

- 报告列表: `https://xxxxxx.cloudfront.net/`
- 最新报告: `https://xxxxxx.cloudfront.net/reports/latest.html`
- 特定报告: `https://xxxxxx.cloudfront.net/reports/report_20251110_120000.html`

## 🔧 在 Lambda 中集成

修改 `collector_handler.py`:

```python
from collection_report_generator import CollectionReportGenerator
from datetime import datetime

def lambda_handler(event, context):
    start_time = datetime.now()
    
    # ... 执行采集 ...
    
    end_time = datetime.now()
    
    # 生成报告
    generator = CollectionReportGenerator()
    
    stats = {
        'start_time': start_time,
        'end_time': end_time,
        'total_resorts': 309,
        'success_count': 285,
        'fail_count': 24,
        'failed_resorts': [
            {'name': 'Resort A', 'error': 'HTTP 429'},
            {'name': 'Resort B', 'error': 'Timeout'},
        ],
        'data_quality': {
            'contact_info_completeness': 78,
            'weather_data_completeness': 95,
            'snow_data_completeness': 88,
        }
    }
    
    # 生成 HTML
    html = generator.generate_report_html(stats)
    
    # 上传报告
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    filename = f"report_{timestamp}.html"
    url = generator.upload_report(html, filename)
    
    # 同时保存为 latest.html
    generator.upload_report(html, 'latest.html')
    
    # 更新索引页面
    generator.update_index()
    
    print(f"✅ 报告已生成: {url}")
    
    return {
        'statusCode': 200,
        'body': {'report_url': url}
    }
```

## 🎨 报告功能

### 报告列表页面
- 显示所有历史报告
- 按时间倒序排列
- 搜索功能（可以搜索日期、时间）
- 点击查看报告详情

### 报告详情页面
- 采集时间和执行时长
- 成功/失败统计
- 成功率进度条
- 失败雪场详情列表
- 数据质量指标
- 返回列表按钮

## 🌐 配置自定义域名（可选）

### 1. 创建 ACM 证书

```bash
# 在 us-east-1 区域创建（CloudFront 要求）
aws acm request-certificate \
  --domain-name reports.steponsnow.com \
  --validation-method DNS \
  --region us-east-1 \
  --profile pp
```

### 2. 修改 Terraform

在 `terraform/reports_cdn.tf` 中启用自定义域名：

```hcl
resource "aws_cloudfront_distribution" "reports" {
  # ...
  
  aliases = ["reports.steponsnow.com"]
  
  viewer_certificate {
    acm_certificate_arn      = "arn:aws:acm:..."
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
```

### 3. 添加 DNS 记录

在你的 DNS 提供商（如 Route 53）添加 CNAME 记录：
```
reports.steponsnow.com → xxxxxx.cloudfront.net
```

## 📊 监控和维护

### 查看 CloudFront 统计

```bash
# CloudFront 请求数
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront \
  --metric-name Requests \
  --dimensions Name=DistributionId,Value=XXXXX \
  --start-time $(date -u -v-1H +"%Y-%m-%dT%H:%M:%S") \
  --end-time $(date -u +"%Y-%m-%dT%H:%M:%S") \
  --period 300 \
  --statistics Sum \
  --region us-east-1 \
  --profile pp
```

### S3 存储成本

- 每个报告约 50KB
- 每小时生成 1 个报告
- 每月约 720 个报告 = 36MB
- S3 成本：约 $0.001/月
- CloudFront 成本：取决于访问量

### 清理旧报告

可以设置 S3 生命周期规则自动删除旧报告：

```hcl
resource "aws_s3_bucket_lifecycle_rule" "reports_cleanup" {
  bucket = aws_s3_bucket.reports.id
  
  enabled = true
  
  expiration {
    days = 30  # 30 天后自动删除
  }
}
```

## 🔍 故障排查

### 报告未生成

```bash
# 检查 Lambda 日志
aws logs tail /aws/lambda/resort-data-collector --follow --profile pp
```

### CloudFront 缓存问题

```bash
# 清除 CloudFront 缓存
aws cloudfront create-invalidation \
  --distribution-id XXXXX \
  --paths "/*" \
  --profile pp
```

### S3 访问权限

```bash
# 检查 Lambda IAM 权限
aws iam get-role-policy \
  --role-name resort-data-lambda-exec-role \
  --policy-name resort-data-lambda-s3-reports \
  --profile pp
```

## 📱 示例截图说明

### 报告列表页面
- 紫色渐变背景
- 卡片式布局
- 搜索筛选框
- 每个报告卡片显示日期和时间

### 报告详情页面
- 4 个统计卡片（总数、成功、失败、成功率）
- 进度条显示成功率
- 失败列表（红色边框）
- 数据质量网格
- 返回按钮

## 🎉 完成！

现在每次 Lambda 采集完成后，都会自动生成漂亮的报告！

访问 CloudFront URL 查看所有报告。

