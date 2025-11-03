# 🏗️ Terraform 基础设施管理

## 📋 用途

Terraform 用于管理 **基础设施**（不包括代码更新）：

- ✅ VPC, 子网, 安全组
- ✅ RDS PostgreSQL
- ✅ ElastiCache Redis  
- ✅ Lambda 函数定义（不管代码）
- ✅ API Gateway
- ✅ ACM 证书
- ✅ Route53 DNS
- ✅ IAM 角色

**Lambda 代码更新** 由 GitHub Actions 自动完成（AWS CLI）

---

## 🚀 首次部署

### 1. 配置变量

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars
```

**必改项**:
```hcl
db_password = "your_secure_password"  # 强密码
aws_profile = "pp"                     # 你的 AWS profile
```

### 2. 初始化

```bash
terraform init
```

### 3. 查看计划

```bash
terraform plan
```

### 4. 部署

```bash
terraform apply
```

**预计时间**: 15-20 分钟（ACM 证书验证需要时间）

---

## 🔄 日常使用

### 只在以下情况运行 Terraform：

#### ✅ 需要运行的场景
- 修改数据库配置（实例类型、存储大小）
- 修改 Lambda 配置（内存、超时、环境变量）
- 修改 VPC 网络配置
- 添加/删除 AWS 资源
- 修改域名配置

#### ❌ 不需要运行的场景  
- 更新 Python 代码 → **GitHub Actions 自动处理**
- 修改 API 逻辑 → **GitHub Actions 自动处理**
- 修改数据采集脚本 → **GitHub Actions 自动处理**

---

## 📝 常用命令

### 查看当前状态
```bash
terraform show
```

### 查看资源列表
```bash
terraform state list
```

### 查看输出
```bash
terraform output

# 查看特定输出
terraform output api_custom_domain_url
terraform output rds_address
```

### 只更新特定资源
```bash
# 只更新 Lambda 配置（不更新代码）
terraform apply -target=aws_lambda_function.api

# 只更新 RDS 配置
terraform apply -target=aws_db_instance.postgresql
```

### 销毁资源（慎重！）
```bash
terraform destroy
```

---

## 🔧 修改配置示例

### 例子 1: 增加 RDS 存储

```hcl
# terraform.tfvars
db_allocated_storage = 50  # 从 20GB → 50GB
```

```bash
terraform plan   # 查看变更
terraform apply  # 应用变更
```

### 例子 2: 修改 Lambda 内存

```hcl
# terraform.tfvars
lambda_memory = 1024  # 从 512MB → 1024MB
```

```bash
terraform apply
```

### 例子 3: 修改采集频率

```hcl
# terraform.tfvars
data_collection_schedule = "cron(0 */6 * * ? *)"  # 改为每 6 小时
```

```bash
terraform apply
```

---

## 🗄️ 初始化数据库

**首次部署后**，需要初始化数据库：

```bash
aws lambda invoke \
  --function-name resort-data-collector \
  --region us-west-2 \
  --profile pp \
  response.json

cat response.json
```

这会：
1. 创建数据库表
2. 采集雪场数据
3. 测试 API

---

## 📊 验证部署

### 1. 检查 API
```bash
curl https://api.steponsnow.com/api/resorts
```

### 2. 查看 RDS
```bash
terraform output rds_address
```

### 3. 查看日志
```bash
aws logs tail /aws/lambda/resort-data-api --follow --profile pp
```

---

## 🐛 常见问题

### Q: 资源已存在错误？

**A**: 导入已存在的资源
```bash
terraform import aws_db_parameter_group.postgresql resort-data-postgres-params
terraform import aws_iam_role.rds_monitoring resort-data-rds-monitoring-role
```

### Q: 状态文件在哪？

**A**: 本地 `terraform.tfstate`（建议添加到 `.gitignore`）

### Q: 如何查看成本？

**A**: 
```bash
# 使用 Infracost
infracost breakdown --path .

# 或查看 AWS Cost Explorer
https://console.aws.amazon.com/cost-management/
```

### Q: 如何回滚？

**A**: 
```bash
# 查看历史
terraform state list

# 恢复到特定状态（如果有备份）
mv terraform.tfstate.backup terraform.tfstate
terraform apply
```

---

## 💰 成本估算

**月成本**: ~$60-65

- NAT Gateway: $32
- RDS (db.t4g.micro): $15
- ElastiCache (cache.t4g.micro): $12
- Lambda + API Gateway: $1-3
- Route53 + ACM: $0.60

---

## 📚 架构说明

```
┌─────────────────────────────────────────┐
│  Terraform (你手动运行)                  │
│  管理: 基础设施                          │
│  频率: 很少 (只在架构变更时)              │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  GitHub Actions (自动运行)               │
│  管理: Lambda 代码                       │
│  频率: 每次代码提交                      │
└─────────────────────────────────────────┘
```

---

## 🔐 安全提示

1. ✅ `terraform.tfvars` 包含密码，不要提交到 Git
2. ✅ 定期轮换数据库密码
3. ✅ 定期更新 Terraform 版本
4. ✅ 使用 IAM 最小权限原则

---

**有问题？查看日志或联系团队！** 🚀
