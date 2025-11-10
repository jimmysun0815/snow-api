# 🏔️ Trail Collector Lambda 部署和使用指南

## 📦 快速部署

### 1. 打包 Lambda 函数

```bash
cd backend-api
./build_trails_lambda.sh
```

这会创建 `trails-collector-lambda.zip` 文件（约 50-70MB）。

### 2. 部署到 AWS

#### 方法 A: 使用 Terraform（推荐）

```bash
# 1. 先上传 ZIP 到 S3
aws s3 cp trails-collector-lambda.zip \
  s3://resort-data-lambda-artifacts-579866932024/trails-collector-lambda.zip \
  --profile pp

# 2. 应用 Terraform 配置
cd terraform
terraform apply -target=aws_lambda_function.trails_collector
```

#### 方法 B: 直接更新 Lambda 代码

```bash
# 如果函数已存在，直接更新代码
aws lambda update-function-code \
  --function-name resort-data-trails-collector \
  --zip-file fileb://trails-collector-lambda.zip \
  --profile pp
```

#### 方法 C: 手动创建函数（如果不存在）

```bash
aws lambda create-function \
  --function-name resort-data-trails-collector \
  --runtime python3.10 \
  --role arn:aws:iam::579866932024:role/resort-data-lambda-exec \
  --handler trails_collector_handler.lambda_handler \
  --zip-file fileb://trails-collector-lambda.zip \
  --timeout 900 \
  --memory-size 2048 \
  --profile pp \
  --vpc-config SubnetIds=subnet-xxx,subnet-yyy,SecurityGroupIds=sg-xxx \
  --environment Variables="{
    POSTGRES_HOST=xxx.rds.amazonaws.com,
    POSTGRES_PORT=5432,
    POSTGRES_USER=app,
    POSTGRES_PASSWORD=your-password,
    POSTGRES_DB=snow,
    REDIS_HOST=xxx.cache.amazonaws.com,
    REDIS_PORT=6379,
    REDIS_DB=0,
    ENVIRONMENT=production
  }"
```

## 🚀 使用方法

### 测试运行（采集 5 个雪场）

```bash
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"limit": 5}' \
  --profile pp \
  response.json

cat response.json
```

### 采集所有雪场

```bash
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{}' \
  --profile pp \
  response.json
```

### 采集特定雪场

```bash
# 按 ID
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"resort_id": 1}' \
  --profile pp \
  response.json

# 按 slug
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"resort_slug": "whistler-blackcomb"}' \
  --profile pp \
  response.json
```

### 采集前 50 个雪场

```bash
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"limit": 50}' \
  --profile pp \
  response.json
```

## 📊 查看日志

```bash
# 实时查看日志
aws logs tail /aws/lambda/resort-data-trails-collector \
  --follow \
  --profile pp

# 查看最近的日志
aws logs tail /aws/lambda/resort-data-trails-collector \
  --since 1h \
  --profile pp
```

## ⚙️ Lambda 配置

- **运行时**: Python 3.10
- **内存**: 2048 MB (2GB)
- **超时**: 900 秒 (15分钟)
- **VPC**: 在私有子网中，可访问 RDS 和 Redis
- **执行间隔**: 每个雪场约 5 秒

## 📝 Payload 参数

Lambda 函数接受以下参数：

```json
{
  "resort_id": 123,        // 可选：只采集指定ID的雪场
  "resort_slug": "vail",   // 可选：只采集指定slug的雪场
  "limit": 10              // 可选：限制采集数量
}
```

## 🎯 推荐执行策略

### 首次运行：分批采集

由于 Lambda 有 15 分钟超时限制，建议分批采集：

```bash
# 第1批：前100个雪场
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"limit": 100}' \
  --profile pp \
  batch1.json

# 等待完成后，查看已采集的雪场
# 然后继续下一批...
```

### 使用循环批量采集

```bash
#!/bin/bash
# 分批采集所有雪场

BATCH_SIZE=50
TOTAL=309

for ((i=0; i<$TOTAL; i+=$BATCH_SIZE)); do
    echo "采集批次 $((i/$BATCH_SIZE + 1))..."
    
    aws lambda invoke \
      --function-name resort-data-trails-collector \
      --payload "{\"limit\": $BATCH_SIZE}" \
      --profile pp \
      batch_$i.json
    
    echo "批次完成，等待 10 秒..."
    sleep 10
done

echo "✅ 所有批次完成！"
```

## 📈 预计时间

- **单个雪场**: ~5 秒
- **100 个雪场**: ~8-10 分钟
- **309 个雪场**: ~25-30 分钟（需要分批）

## ⚠️ 注意事项

1. **Lambda 超时限制**: 最多 15 分钟
   - 建议每批不超过 150 个雪场
   - 使用 `limit` 参数控制批次大小

2. **OpenStreetMap API 限流**
   - 脚本已设置每个雪场间隔 5 秒
   - 避免并发运行多个 Lambda

3. **内存使用**
   - 已配置 2GB 内存
   - 足够处理雪道数据和依赖库

4. **VPC 配置**
   - 必须在 VPC 内才能访问 RDS
   - 需要 NAT Gateway 访问外部 OSM API

## 🔍 故障排查

### Lambda 超时

如果采集超时，减少批次大小：

```bash
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"limit": 50}' \
  --profile pp \
  response.json
```

### 查看错误详情

```bash
# 查看最近的错误日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/resort-data-trails-collector \
  --filter-pattern "ERROR" \
  --profile pp
```

### 检查函数配置

```bash
aws lambda get-function-configuration \
  --function-name resort-data-trails-collector \
  --profile pp
```

## 💡 提示

1. **首次运行建议测试**：先用 `{"limit": 5}` 测试
2. **查看实时日志**：运行时开另一个终端查看日志
3. **定期采集**：雪道数据变化不频繁，每月采集一次即可
4. **分批执行**：避免超时，推荐每批 50-100 个雪场

## 🎯 完整执行示例

```bash
# 1. 打包
./build_trails_lambda.sh

# 2. 上传到 S3
aws s3 cp trails-collector-lambda.zip \
  s3://resort-data-lambda-artifacts-579866932024/ \
  --profile pp

# 3. 更新 Lambda
aws lambda update-function-code \
  --function-name resort-data-trails-collector \
  --s3-bucket resort-data-lambda-artifacts-579866932024 \
  --s3-key trails-collector-lambda.zip \
  --profile pp

# 4. 测试运行
aws lambda invoke \
  --function-name resort-data-trails-collector \
  --payload '{"limit": 5}' \
  --profile pp \
  test_response.json

# 5. 查看结果
cat test_response.json

# 6. 查看日志
aws logs tail /aws/lambda/resort-data-trails-collector \
  --profile pp

# 7. 如果测试成功，分批采集所有雪场
for i in {0..6}; do
    START=$((i * 50))
    echo "Batch $((i+1)): Starting from resort $START"
    
    aws lambda invoke \
      --function-name resort-data-trails-collector \
      --payload '{"limit": 50}' \
      --profile pp \
      batch_$i.json
    
    sleep 10
done
```

---

**准备好了吗？开始采集！** 🎿⛷️

