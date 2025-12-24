# Prod 环境 - 通知系统部署

## 📋 概述

这个目录包含 **Prod 环境**的通知系统 Lambda 配置。

### 架构设计

```
Dev 环境（backend-api/terraform/）:
├── VPC + Subnets + Security Groups ✅ (共用)
├── RDS + Redis ✅ (共用)
├── 雪场数据采集 Lambda ✅ (共用)
└── Dev 通知 Lambda ✅ (连接 Dev Supabase)

Prod 环境（prod/）:
└── Prod 通知 Lambda ✅ (连接 Prod Supabase)
    - 使用 Dev 的 VPC
    - 使用 Dev 的 IAM Role
    - 使用 Dev 的 S3 Bucket
    - 独立的 Supabase 配置
```

## 🚀 部署步骤

### 1. 获取 Prod Supabase Service Key

去 Prod Supabase Dashboard:
```
https://supabase.com/dashboard/project/jbucqclsoqcjvnefiyyw/settings/api
```

复制 **service_role (secret)** key，更新 `terraform.tfvars`:
```hcl
prod_supabase_service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 2. 初始化 Terraform

```bash
cd prod
terraform init
```

### 3. 检查配置

```bash
terraform plan
```

这会显示将要创建的资源：
- ✅ Lambda Function: `resort-data-prod-notification-processor`
- ✅ Lambda Function URL (用于 Webhook)
- ✅ CloudWatch Log Group

### 4. 部署

```bash
terraform apply
```

### 5. 获取 Lambda Function URL

```bash
terraform output lambda_function_url
```

输出示例：
```
https://xxxxx.lambda-url.us-west-2.on.aws/
```

### 6. 在 Prod Supabase 配置 Webhook

去 Prod Supabase SQL Editor:
```
https://supabase.com/dashboard/project/jbucqclsoqcjvnefiyyw/sql
```

执行迁移 069，将 `webhook_url` 改为上面的 Lambda URL:

```sql
-- 1. 启用 pg_net 扩展
CREATE EXTENSION IF NOT EXISTS pg_net;

-- 2. 执行迁移 069（修改 webhook_url）
-- 从 app/snow_resort_app/supabase/migrations/069_switch_to_webhook_realtime_push.sql
-- 将两个函数中的 webhook_url 改为你的 Lambda URL
```

## 🧪 测试

### 测试通知发送

在 Prod Supabase SQL Editor:

```sql
-- 创建测试拼车申请
INSERT INTO carpool_applications (carpool_id, applicant_id, status)
VALUES (1, 'test-user-id', 'pending');

-- 检查是否收到通知
-- （通知应该通过 Webhook 实时发送，不会留在 queue 中）
```

### 查看 Lambda 日志

```bash
aws logs tail /aws/lambda/resort-data-prod-notification-processor --follow --profile pp
```

应该看到：
```
📨 收到事件: ...
🌐 处理 HTTP 请求
📦 Webhook 数据: ...
✅ 通知发送成功
```

## 📊 资源列表

| 资源 | 名称 | 说明 |
|------|------|------|
| Lambda | `resort-data-prod-notification-processor` | Prod 通知处理器 |
| Lambda URL | `https://xxxxx.lambda-url.us-west-2.on.aws/` | Webhook 入口 |
| CloudWatch | `/aws/lambda/resort-data-prod-notification-processor` | 日志组 |

## 🔗 依赖的 Dev 环境资源

以下资源来自 Dev 环境，不会重复创建：

- ✅ VPC: `resort-data-vpc`
- ✅ Subnets: `resort-data-private-*`
- ✅ Security Group: `resort-data-lambda-sg`
- ✅ IAM Role: `resort-data-lambda-exec-role`
- ✅ S3 Bucket: `resort-data-lambda-artifacts`

## 🗑️ 清理资源

如果需要删除 Prod 通知系统：

```bash
cd prod
terraform destroy
```

这只会删除 Prod 通知 Lambda，不会影响 Dev 环境和雪场数据采集。

## ⚠️ 注意事项

1. **Lambda 代码共用**: Prod 和 Dev 使用同一个 S3 上的 `sqs-notification-processor.zip`
2. **VPC 共用**: Prod Lambda 运行在 Dev 的 VPC 中
3. **Supabase 独立**: Prod Lambda 连接到 Prod Supabase
4. **Firebase 共用**: Dev 和 Prod 使用同一个 Firebase 项目

## 📝 更新 Lambda 代码

当更新通知处理代码时：

```bash
# 1. 在 backend-api 目录打包新代码
cd ../backend-api
mkdir -p lambda_package
cp sqs_notification_processor.py push_service.py lambda_package/
pip install -r requirements.txt -t lambda_package/
cd lambda_package
zip -r ../sqs-notification-processor.zip .
cd ..

# 2. 上传到 S3
aws s3 cp sqs-notification-processor.zip s3://resort-data-lambda-artifacts/ --profile pp

# 3. 更新 Prod Lambda
cd ../prod
terraform apply -replace="aws_lambda_function.prod_sqs_notification_processor"
```

或者使用 AWS CLI 直接更新：

```bash
aws lambda update-function-code \
  --function-name resort-data-prod-notification-processor \
  --s3-bucket resort-data-lambda-artifacts \
  --s3-key sqs-notification-processor.zip \
  --profile pp
```

