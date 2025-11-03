# Terraform Infrastructure for Resort Data

AWS 基础设施即代码 (Infrastructure as Code)

## 快速开始

### 1. 配置文件

```bash
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars  # 修改配置
```

### 2. 初始化

```bash
terraform init
```

### 3. 查看计划

```bash
terraform plan -var="db_password=YOUR_PASSWORD"
```

### 4. 应用

```bash
terraform apply -var="db_password=YOUR_PASSWORD"
```

### 5. 查看输出

```bash
terraform output
terraform output api_gateway_url
```

## 资源列表

- **VPC**: 10.0.0.0/16
- **RDS PostgreSQL**: db.t4g.micro, 20GB
- **ElastiCache Redis**: cache.t4g.micro
- **Lambda API**: Python 3.11, 512MB
- **Lambda Collector**: Python 3.11, 1024MB
- **API Gateway**: REST API
- **EventBridge**: 定时任务

## 成本估算

约 **$27-30/月**

## 销毁资源

```bash
terraform destroy -var="db_password=YOUR_PASSWORD"
```

**警告**: 这会删除所有资源,包括数据库！

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.tf` | Provider 和 Backend 配置 |
| `variables.tf` | 变量定义 |
| `vpc.tf` | VPC 网络配置 |
| `security_groups.tf` | 安全组 |
| `rds.tf` | PostgreSQL 数据库 |
| `elasticache.tf` | Redis 缓存 |
| `lambda.tf` | Lambda 函数 |
| `api_gateway.tf` | API Gateway |
| `eventbridge.tf` | 定时任务 |
| `outputs.tf` | 输出变量 |

详细文档请查看 [DEPLOYMENT.md](../DEPLOYMENT.md)

