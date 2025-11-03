# 🏔️ Resort Data Backend API

雪场数据采集和 REST API 服务

## 📁 项目结构

```
backend-api/
├── .github/workflows/
│   └── deploy.yml           # GitHub Actions 自动部署
├── terraform/              # AWS 基础设施配置
│   ├── main.tf
│   ├── variables.tf
│   └── ...
├── *.py                    # Python 源代码
│   ├── api.py              # Flask API
│   ├── collect_data.py     # 数据采集
│   ├── lambda_handler.py   # Lambda 入口
│   └── ...
└── requirements.txt        # Python 依赖
```

---

## 🚀 快速开始

### 本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp env.template .env
vim .env

# 3. 初始化数据库
python init_database.py

# 4. 采集数据
python collect_data.py

# 5. 启动 API
python api.py
```

访问: http://localhost:8000/api/resorts

---

## ☁️ AWS 部署

### 架构说明

```
┌─────────────────────────────────────────┐
│  Terraform (手动运行 - 只在架构变更时)    │
│  管理: RDS, Redis, VPC, IAM, DNS, 等    │
│  频率: 很少                              │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  GitHub Actions (自动运行)               │
│  管理: Lambda 代码更新                   │
│  频率: 每次代码提交 (~10秒)              │
└─────────────────────────────────────────┘
```

### 首次部署

#### 1. 配置 GitHub Secrets
   
在 GitHub 仓库 Settings → Secrets 添加:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

#### 2. 部署基础设施（Terraform）

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars  # 设置密码和 AWS profile

terraform init
terraform plan
terraform apply
```

**预计时间**: 15-20 分钟

#### 3. 初始化数据库

```bash
aws lambda invoke \
  --function-name resort-data-collector \
  --region us-west-2 \
  --profile pp \
  response.json
```

#### 4. 推送代码（触发自动部署）

```bash
git add .
git commit -m "Initial code deployment"
git push origin main
```

GitHub Actions 会自动更新 Lambda 代码（~10秒）

---

## 🔄 日常开发流程

修改代码后，**只需要推送**：

```bash
# 1. 修改代码
vim api.py

# 2. 提交推送
git add .
git commit -m "Update API"
git push origin main
```

GitHub Actions 会自动更新 Lambda！约 **10 秒**完成。

### 修改基础设施

只在以下情况运行 Terraform：
- 修改数据库/Redis 配置
- 修改 Lambda 配置（内存、超时、环境变量）
- 修改 VPC/网络配置

```bash
cd terraform
vim terraform.tfvars  # 修改配置
terraform apply
```

---

## 📡 API 端点

部署后的 API 地址: `https://{api-id}.execute-api.us-west-2.amazonaws.com/prod`

### 雪场数据

```bash
GET /api/resorts                    # 获取所有雪场
GET /api/resorts/{id}              # 获取单个雪场
GET /api/resorts/slug/{slug}       # 按 slug 获取
GET /api/resorts/open              # 获取开放的雪场
GET /api/resorts/search?q=万龙     # 搜索雪场
GET /api/resorts/nearby?lat=&lon=  # 附近雪场
```

### 雪道数据

```bash
GET /api/resorts/{id}/trails       # 获取雪道 (by ID)
GET /api/resorts/slug/{slug}/trails # 获取雪道 (by slug)
```

### 系统

```bash
GET /api/status                    # 系统状态
```

---

## 🏗️ AWS 架构

```
┌──────────────────────────────────────────────┐
│  GitHub Push                                 │
└────────────┬─────────────────────────────────┘
             ↓
┌──────────────────────────────────────────────┐
│  GitHub Actions                              │
│  ├─ Build Lambda packages                   │
│  ├─ Run Terraform                            │
│  └─ Update Lambda functions                 │
└────────────┬─────────────────────────────────┘
             ↓
┌──────────────────────────────────────────────┐
│  AWS Infrastructure                          │
│  ├─ API Gateway → Lambda API                │
│  ├─ EventBridge → Lambda Collector (定时)   │
│  ├─ RDS PostgreSQL (db.t4g.micro, 20GB)     │
│  └─ ElastiCache Redis (cache.t4g.micro)     │
└──────────────────────────────────────────────┘
```

**成本**: ~$60-65/月（包含 NAT Gateway）

---

## 📊 监控

### 查看日志

```bash
# API Lambda 日志
aws logs tail /aws/lambda/resort-data-api --follow

# Collector Lambda 日志
aws logs tail /aws/lambda/resort-data-collector --follow

# API Gateway 日志
aws logs tail /aws/apigateway/resort-data --follow
```

### 手动触发数据采集

```bash
aws lambda invoke \
  --function-name resort-data-collector \
  --region us-west-2 \
  --profile pp \
  response.json

cat response.json
```

---

## 🔧 常用命令

### Terraform

```bash
cd terraform

# 查看资源
terraform show

# 查看输出
terraform output

# 获取 API URL
terraform output -raw api_gateway_url

# 销毁资源 (慎重！)
terraform destroy
```

### 本地测试

```bash
# 运行 API
python api.py

# 采集数据
python collect_data.py

# 采集雪道
python collect_trails.py

# 初始化数据库
python init_database.py
```

---

## 📝 环境变量

### 本地开发 (.env)

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_DB=snow

# Redis
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0

# 缓存
CACHE_TTL=300

# 采集间隔
DATA_COLLECTION_INTERVAL=3600
```

### AWS Lambda (自动配置)

Lambda 环境变量由 Terraform 自动配置:
- `POSTGRES_HOST` - RDS 端点
- `REDIS_HOST` - ElastiCache 端点
- 其他配置...

---

## 🐛 故障排查

### 部署失败

查看 GitHub Actions 日志:
- GitHub → Actions → 点击失败的 workflow

### Lambda 超时

增加 timeout:
```hcl
# terraform/variables.tf
variable "lambda_timeout" {
  default = 60  # 增加到 60 秒
}
```

### 数据库连接失败

检查安全组和 VPC 配置:
```bash
aws ec2 describe-security-groups --group-ids sg-xxxxx
aws lambda get-function-configuration --function-name resort-data-api
```

---

## 📚 文档

- [完整部署指南](../DEPLOYMENT.md)
- [部署检查清单](../DEPLOYMENT_CHECKLIST.md)
- [Terraform 配置](terraform/README.md)

---

## 💰 成本详情

**月成本: ~$60-65**

### 成本构成
- **NAT Gateway**: ~$32/月（必需，用于 Collector 访问外网）
- **RDS PostgreSQL** (db.t4g.micro): ~$15/月
- **ElastiCache Redis** (cache.t4g.micro): ~$12/月
- **Lambda + API Gateway**: ~$1-3/月
- **数据传输**: ~$2-3/月

### 💡 优化建议
1. ✅ **降低采集频率到每6小时**: 节省 ~$2-3/月（已默认配置）
2. **购买 RDS Reserved Instance**: 节省 ~$5/月
3. **移除 NAT Gateway**: 不推荐（安全风险大）

### 关于 NAT Gateway
NAT Gateway 是必需的，因为:
- Collector Lambda 需要访问外部网站抓取雪场数据
- RDS 和 Redis 在 VPC 私有子网（安全最佳实践）
- $32/月是安全架构的合理成本

---

## 🤝 贡献

欢迎提交 Pull Request！

---

## 📄 License

MIT License

---

**有问题？查看日志或联系团队！** 🚀
