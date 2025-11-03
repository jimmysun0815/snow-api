# 🌐 使用自定义域名部署指南

## 📋 前置条件

- ✅ 域名已在 Route53 托管（`steponsnow.com`）
- ✅ AWS CLI 已配置 profile `pp`
- ✅ 本地 Terraform 已安装

---

## 🔧 解决本地 TLS 证书问题

### 问题：`x509: OSStatus -26276`

这是 macOS 系统证书验证问题，有两个解决方案：

### 方案 1: 使用本地 Backend（快速测试）

临时注释掉 S3 backend，使用本地状态文件：

```hcl
# terraform/main.tf

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # 临时注释掉 S3 backend
  # backend "s3" {
  #   bucket  = "resort-data-terraform-state"
  #   key     = "terraform.tfstate"
  #   region  = "us-west-2"
  #   profile = "pp"
  # }
}
```

**注意**: 本地 backend 仅用于测试，生产环境建议使用 S3。

---

### 方案 2: 修复 macOS 证书（推荐）

```bash
# 1. 更新系统证书
sudo /usr/sbin/update-ca-certificates

# 2. 重新安装 AWS CLI（如果需要）
brew reinstall awscli

# 3. 清理 Python 证书缓存
pip3 install --upgrade certifi

# 4. 设置环境变量（临时）
export GODEBUG=x509ignoreCN=0
```

---

## 🚀 部署步骤

### 步骤 1: 验证 Route53 托管区域

```bash
# 查看托管区域
aws route53 list-hosted-zones --profile pp

# 应该看到 steponsnow.com 的 Zone ID
```

如果没有，手动创建：

```bash
aws route53 create-hosted-zone \
  --name steponsnow.com \
  --caller-reference $(date +%s) \
  --profile pp
```

---

### 步骤 2: 初始化 Terraform（使用本地 backend）

```bash
cd terraform

# 清理旧缓存
rm -rf .terraform .terraform.lock.hcl

# 初始化
terraform init
```

---

### 步骤 3: 验证配置

```bash
# 查看将要创建的资源
terraform plan

# 应该看到：
# - ACM 证书
# - Route53 DNS 验证记录
# - API Gateway 自定义域名
# - RDS、Redis、Lambda 等
```

---

### 步骤 4: 部署

```bash
# 应用配置
terraform apply

# 输入 yes 确认
```

**预计时间**: 20-25 分钟（ACM 证书验证需要 5-10 分钟）

---

### 步骤 5: 验证部署

```bash
# 查看输出
terraform output

# 应该看到：
# - api_custom_domain_url = "https://api.steponsnow.com"
# - acm_certificate_status = "ISSUED"
```

---

## 🧪 测试 API

### 测试自定义域名

```bash
# 等待 DNS 传播（1-5 分钟）
curl https://api.steponsnow.com/api/resorts

# 如果返回 502，等待几分钟（Lambda 冷启动）
```

### 测试默认 URL

```bash
# 获取默认 URL
API_URL=$(terraform output -raw api_gateway_url)

# 测试
curl $API_URL/api/resorts
```

---

## 📊 部署后配置

### 1. 初始化数据库

```bash
# 手动触发 Collector Lambda
aws lambda invoke \
  --function-name resort-data-collector \
  --region us-west-2 \
  --profile pp \
  response.json

cat response.json
```

### 2. 验证证书

```bash
# 查看证书详情
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw acm_certificate_arn) \
  --region us-west-2 \
  --profile pp
```

### 3. 验证 DNS

```bash
# 查看 DNS 记录
dig api.steponsnow.com

# 应该看到 A 记录指向 API Gateway
```

---

## 🔄 迁移到 S3 Backend

测试成功后，迁移到 S3 backend：

### 1. 创建 S3 Bucket

```bash
aws s3 mb s3://resort-data-terraform-state --region us-west-2 --profile pp

aws s3api put-bucket-versioning \
  --bucket resort-data-terraform-state \
  --versioning-configuration Status=Enabled \
  --profile pp
```

### 2. 取消注释 S3 backend

```hcl
# terraform/main.tf
backend "s3" {
  bucket  = "resort-data-terraform-state"
  key     = "terraform.tfstate"
  region  = "us-west-2"
  profile = "pp"
}
```

### 3. 迁移状态文件

```bash
terraform init -migrate-state

# 输入 yes 确认迁移
```

---

## 🌍 DNS 传播时间

| 类型 | 预计时间 |
|------|---------|
| **ACM 证书验证** | 5-10 分钟 |
| **Route53 DNS 更新** | 1-5 分钟 |
| **全球 DNS 传播** | 最多 48 小时 |

**加速 DNS 传播**:
```bash
# 清除本地 DNS 缓存
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

---

## 🐛 常见问题

### Q1: ACM 证书一直是 PENDING_VALIDATION？

**A**: 检查 Route53 DNS 验证记录是否正确创建

```bash
# 查看验证记录
aws route53 list-resource-record-sets \
  --hosted-zone-id $(aws route53 list-hosted-zones --query "HostedZones[?Name=='steponsnow.com.'].Id" --output text --profile pp) \
  --profile pp
```

---

### Q2: curl https://api.steponsnow.com 返回 502？

**A**: 等待 2-3 分钟，Lambda 冷启动需要时间

```bash
# 查看 Lambda 日志
aws logs tail /aws/lambda/resort-data-api --follow --profile pp
```

---

### Q3: DNS 解析失败？

**A**: 检查 Route53 记录是否正确

```bash
# 查看 A 记录
dig api.steponsnow.com

# 如果没有记录，手动创建：
terraform apply -replace="aws_route53_record.api"
```

---

### Q4: 证书不受信任？

**A**: 确保证书已验证

```bash
# 查看证书状态
aws acm list-certificates --region us-west-2 --profile pp

# Status 应该是 ISSUED
```

---

## 💰 额外成本

使用自定义域名的额外成本：

| 服务 | 月成本 |
|------|--------|
| **ACM 证书** | $0（免费） |
| **Route53 托管区域** | $0.50/月 |
| **DNS 查询** | $0.40/百万次（通常 < $0.10/月） |

**总额外成本**: ~$0.60/月

---

## 📚 参考资料

- [AWS ACM 文档](https://docs.aws.amazon.com/acm/)
- [API Gateway 自定义域名](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-custom-domains.html)
- [Route53 文档](https://docs.aws.amazon.com/route53/)

---

**部署愉快！** 🎉

如有问题，查看 CloudWatch Logs 或 GitHub Issues。

