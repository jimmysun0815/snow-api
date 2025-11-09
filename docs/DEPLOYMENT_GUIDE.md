# SQS + Lambda + Firebase 实时推送部署指南

## 📋 架构说明

```
数据库触发器 → Supabase Edge Function → AWS SQS → Lambda → Firebase → 设备
    (1ms)              (100ms)           (1-2s)    (500ms)   (500ms)
                                                            
总延迟: 2-3秒（vs 原来的30-60秒）
```

## 💰 费用分析

**完全免费！** ✅

| 服务 | 免费额度 | 预计使用 | 费用 |
|------|---------|---------|------|
| SQS | 100万次请求/月 | ~3万次/月 | $0 |
| Lambda | 100万次请求/月 | ~3万次/月 | $0 |
| Lambda 计算 | 400,000 GB-秒/月 | ~7,500 GB-秒/月 | $0 |
| CloudWatch Logs | 5GB/月 | ~150MB/月 | $0 |

**只有当每月通知量超过 100万次时才会产生费用（约 $0.40/月）**

---

## 🚀 部署步骤

### 第1步：准备 Terraform 变量

在 `backend-api/terraform/terraform.tfvars` 中添加：

```hcl
# Supabase 配置
supabase_url         = "https://your-project.supabase.co"
supabase_service_key = "your-service-role-key"

# Firebase 配置（从 Firebase Console → Project Settings → Service Accounts 获取）
firebase_project_id     = "your-project-id"
firebase_private_key_id = "your-private-key-id"
firebase_private_key    = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
firebase_client_email   = "firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com"
firebase_client_id      = "123456789"
```

### 第2步：部署 AWS 基础设施

```bash
cd backend-api/terraform

# 初始化 Terraform
terraform init

# 查看将要创建的资源
terraform plan

# 部署（需要确认）
terraform apply
```

**创建的资源：**
- ✅ SQS 队列（push-notifications）
- ✅ SQS 死信队列（push-notifications-dlq）
- ✅ Lambda 函数（sqs-notification-processor）
- ✅ IAM 角色和权限
- ✅ CloudWatch 日志组和告警
- ✅ IAM 用户（供 Supabase 使用）

### 第3步：记录 Terraform Outputs

```bash
# 获取 SQS 队列 URL
terraform output sqs_queue_url

# 获取 AWS 访问密钥（供 Supabase 使用）
terraform output supabase_aws_access_key_id
terraform output supabase_aws_secret_access_key
```

**保存这些值，下一步需要用到！**

### 第4步：打包 Lambda 函数

```bash
cd backend-api

# 安装依赖到临时目录
pip install -r requirements.txt -t ./lambda_package

# 复制代码文件
cp sqs_notification_processor.py lambda_package/
cp push_service.py lambda_package/

# 打包
cd lambda_package
zip -r ../sqs-notification-processor.zip .
cd ..

# 上传到 S3（假设你的 bucket 是 your-lambda-artifacts）
aws s3 cp sqs-notification-processor.zip s3://your-lambda-artifacts/

# 或者直接通过 Terraform 部署（推荐）
terraform apply
```

### 第5步：部署 Supabase Edge Function

#### 5.1 创建 Edge Function

```bash
cd app/snow_resort_app
supabase functions new send-notification-to-sqs
```

#### 5.2 复制代码

将 `backend-api/supabase-edge-functions/send-notification-to-sqs.ts` 的内容复制到：
```
supabase/functions/send-notification-to-sqs/index.ts
```

#### 5.3 设置 Secrets

在 Supabase Dashboard → Project Settings → Edge Functions → Secrets 添加：

| Secret Name | Value | 来源 |
|------------|-------|------|
| `AWS_REGION` | `us-east-1` | 你的 AWS 区域 |
| `AWS_ACCESS_KEY_ID` | `AKIAxxxx` | Terraform output |
| `AWS_SECRET_ACCESS_KEY` | `xxxxx` | Terraform output |
| `AWS_SQS_QUEUE_URL` | `https://sqs.us-east-1.amazonaws.com/xxx` | Terraform output |

#### 5.4 部署 Edge Function

```bash
supabase functions deploy send-notification-to-sqs
```

### 第6步：修改数据库触发器

#### 6.1 启用 HTTP 扩展

```sql
-- 在 Supabase SQL Editor 中运行
CREATE EXTENSION IF NOT EXISTS http;
```

#### 6.2 创建迁移文件

```bash
cd app/snow_resort_app
supabase migration new sqs_integration
```

#### 6.3 编辑迁移文件

将以下内容复制到新创建的迁移文件中：

```sql
-- 创建调用 Edge Function 的函数
CREATE OR REPLACE FUNCTION send_notification_to_sqs(
    p_user_id UUID,
    p_notification_type TEXT,
    p_title TEXT,
    p_body TEXT,
    p_data JSONB DEFAULT '{}'::JSONB
)
RETURNS BOOLEAN AS $$
DECLARE
    v_edge_function_url TEXT := 'https://YOUR_PROJECT_REF.supabase.co/functions/v1/send-notification-to-sqs';
    v_service_key TEXT := 'YOUR_SERVICE_ROLE_KEY';
    v_response http_response;
BEGIN
    -- 调用 Edge Function
    SELECT * INTO v_response
    FROM http((
        'POST',
        v_edge_function_url,
        ARRAY[
            http_header('Authorization', 'Bearer ' || v_service_key),
            http_header('Content-Type', 'application/json')
        ],
        'application/json',
        jsonb_build_object(
            'user_id', p_user_id::TEXT,
            'notification_type', p_notification_type,
            'title', p_title,
            'body', p_body,
            'data', p_data
        )::TEXT
    )::http_request);
    
    -- 检查响应
    IF v_response.status >= 200 AND v_response.status < 300 THEN
        RAISE NOTICE '✅ 通知已发送到 SQS: user_id=%, type=%', p_user_id, p_notification_type;
        RETURN TRUE;
    ELSE
        RAISE WARNING '❌ 发送到 SQS 失败: status=%, response=%', v_response.status, v_response.content;
        RETURN FALSE;
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING '❌ 调用 Edge Function 失败: %', SQLERRM;
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 修改拼车通知触发器
CREATE OR REPLACE FUNCTION notify_carpool_application()
RETURNS TRIGGER AS $$
DECLARE
    owner_id UUID;
    applicant_name TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- 获取拼车发布者 ID
        SELECT user_id INTO owner_id FROM carpool_posts WHERE id = NEW.carpool_id;
        
        -- 获取申请者昵称
        applicant_name := get_user_display_name(NEW.applicant_id);
        
        -- 插入到 notifications 表（应用内通知）
        INSERT INTO notifications (user_id, type, title, content, related_id)
        VALUES (
            owner_id,
            'carpool_new_signup',
            '新的拼车报名',
            applicant_name || ' 报名了你的拼车',
            NEW.id
        );
        
        -- 发送到 SQS（Firebase 推送）
        PERFORM send_notification_to_sqs(
            owner_id,
            'carpool_application',
            '新的拼车报名',
            applicant_name || ' 报名了你的拼车',
            jsonb_build_object(
                'type', 'carpool_application',
                'carpool_id', NEW.carpool_id::TEXT,
                'application_id', NEW.id::TEXT,
                'applicant_id', NEW.applicant_id::TEXT
            )
        );
    
    ELSIF TG_OP = 'UPDATE' AND OLD.status != NEW.status THEN
        -- 申请状态变更通知
        IF NEW.status = 'approved' THEN
            INSERT INTO notifications (user_id, type, title, content, related_id)
            VALUES (
                NEW.applicant_id,
                'carpool_signup_approved',
                '拼车报名已通过',
                '你的拼车报名已被接受',
                NEW.id
            );
            
            PERFORM send_notification_to_sqs(
                NEW.applicant_id,
                'carpool_approved',
                '拼车报名已通过',
                '你的拼车报名已被接受',
                jsonb_build_object(
                    'type', 'carpool_approved',
                    'carpool_id', NEW.carpool_id::TEXT,
                    'application_id', NEW.id::TEXT
                )
            );
            
        ELSIF NEW.status = 'rejected' THEN
            INSERT INTO notifications (user_id, type, title, content, related_id)
            VALUES (
                NEW.applicant_id,
                'carpool_signup_rejected',
                '拼车报名未通过',
                '很抱歉，你的拼车报名未被接受',
                NEW.id
            );
            
            PERFORM send_notification_to_sqs(
                NEW.applicant_id,
                'carpool_rejected',
                '拼车报名未通过',
                '很抱歉，你的拼车报名未被接受',
                jsonb_build_object(
                    'type', 'carpool_rejected',
                    'carpool_id', NEW.carpool_id::TEXT,
                    'application_id', NEW.id::TEXT
                )
            );
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 类似地修改拼房通知触发器（代码类似，这里省略）
```

**重要：替换其中的占位符：**
- `YOUR_PROJECT_REF`: 你的 Supabase 项目引用
- `YOUR_SERVICE_ROLE_KEY`: 你的 Supabase Service Role Key

#### 6.4 应用迁移

```bash
supabase db push
```

### 第7步：测试

#### 7.1 测试 Edge Function

```bash
curl -X POST \
  'https://YOUR_PROJECT_REF.supabase.co/functions/v1/send-notification-to-sqs' \
  -H 'Authorization: Bearer YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "test-user-uuid",
    "notification_type": "test",
    "title": "测试通知",
    "body": "这是一条测试消息",
    "data": {"type": "test"}
  }'
```

期望输出：
```json
{"success": true, "message_id": "xxx"}
```

#### 7.2 检查 SQS 队列

```bash
# 查看队列消息数
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw sqs_queue_url) \
  --attribute-names ApproximateNumberOfMessages
```

#### 7.3 查看 Lambda 日志

```bash
# 实时查看日志
aws logs tail /aws/lambda/$(terraform output -raw lambda_function_name) --follow
```

#### 7.4 端到端测试

1. 在 App 中报名拼车
2. 预期：2-3秒内收到推送通知
3. 检查 CloudWatch 日志确认处理成功

---

## 📊 监控

### CloudWatch 告警

已自动配置以下告警：

1. **死信队列告警** - 有消息进入死信队列时触发
2. **消息积压告警** - 消息在队列中超过5分钟时触发
3. **Lambda 错误告警** - Lambda 错误率过高时触发

### 查看指标

```bash
# 查看 SQS 指标
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=your-queue-name \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average
```

---

## 🔧 故障排查

### 问题1：通知未收到

**检查清单：**
1. SQS 队列是否有消息？
   ```bash
   aws sqs get-queue-attributes --queue-url YOUR_QUEUE_URL --attribute-names All
   ```

2. Lambda 是否触发？
   ```bash
   aws logs tail /aws/lambda/YOUR_FUNCTION_NAME
   ```

3. Firebase token 是否有效？
   - 查看 `device_tokens` 表
   - 检查 token 是否过期

### 问题2：消息进入死信队列

```bash
# 查看死信队列消息
aws sqs receive-message --queue-url YOUR_DLQ_URL

# 分析失败原因
aws logs filter-pattern "ERROR" /aws/lambda/YOUR_FUNCTION_NAME
```

### 问题3：延迟过高

**可能原因：**
- Lambda 冷启动（首次调用 ~3秒）
- Firebase API 延迟
- 批处理等待时间（最多5秒）

**优化方案：**
- 减少批处理时间（修改 `maximum_batching_window_in_seconds`）
- 使用 Lambda Provisioned Concurrency（需付费）

---

## 🔄 回滚方案

如果新架构出现问题，快速回滚：

```bash
# 1. 禁用 Lambda 事件源映射
aws lambda delete-event-source-mapping --uuid YOUR_MAPPING_UUID

# 2. 恢复旧的轮询 Lambda
aws events enable-rule --name YOUR_OLD_RULE_NAME

# 3. 重新部署旧触发器
supabase db push --file migrations/067_add_push_queue_support.sql
```

---

## 📝 总结

### 改进对比

| 指标 | 旧架构（轮询） | 新架构（SQS） |
|------|--------------|--------------|
| 延迟 | 30-60秒 | 2-3秒 |
| 费用 | $0 | $0 |
| 可靠性 | 中 | 高（自动重试） |
| 监控 | 基础 | 完善（CloudWatch） |
| 扩展性 | 一般 | 自动扩展 |

### 下一步

- ✅ 部署成功后，监控第一周的运行情况
- ✅ 根据实际流量调整批处理大小
- ✅ 考虑添加邮件/短信通知（订阅 SNS Topic）

