# 雪场数据库：AWS RDS → Supabase Prod 切换手册（2026-11）

目标：Lambda 改连 Supabase Prod，移出 VPC，然后下线 RDS + ElastiCache + NAT Gateway（约 -$64/月）。

代码侧已完成并在本地验证（本地 Supabase + 真实 OnTheSnow / Open-Meteo 采集）：
- `config.py` / `db_manager.py`：识别 Supabase pooler → NullPool、不跑 `create_all`；
  Redis 只有显式配置 `REDIS_URL`/`REDIS_HOST` 才启用，否则直接查库
- `check_snow_and_notify.py`：优先用 `DATABASE_URL`
- `terraform/`：5 个 Lambda（api / collector / contact-collector / trails-collector / snow-checker）
  环境变量改为 `DATABASE_URL`，`vpc_config` 置空（provider 4.x 必须显式空列表才会真正解绑）
- 删除 `.github/workflows/sync-resorts.yml`，`sync_resorts_to_supabase.py` 加了保护
  （它「先删光 resorts 再重插」，resorts 上的 CASCADE 外键会连带清空全部时序数据）

## 第 1 步：Supabase Prod schema + 数据

1. app 仓库：`cd app/snow_resort_app && supabase link --project-ref jbucqclsoqcjvnefiyyw && supabase db push`
   （推 `20261102000001`–`000009`，含 151 的四张时序表）
2. Prod SQL Editor 执行 `resort-data/migration_export/import_resorts_to_supabase.sql`
   - 已有 262 行只补 `boundary/source_id/notes/created_at`，另插 12 行 `enabled=false`
   - 幂等；最后一条 SELECT 应返回 `274 | 12 | 12`
   - 时序表不导入：CSV 早于 7 天保留期，导了也会当天被清理；由第 4 步的采集写新数据
3. GitHub `snow-api` → Actions → *Sync Resorts to Supabase* → ⋯ → **Disable workflow**
   （代码里已删除该 workflow，但在第 3 步 push 之前它仍可能被定时触发）

## 第 2 步：后端代码先上线（此时仍连 RDS）

代码向后兼容：没有 `DATABASE_URL` 时照旧用 `POSTGRES_*`，`REDIS_HOST` 还在就继续用 ElastiCache。

```bash
cd backend-api && git push origin main     # 触发 deploy.yml，部署新代码（含 OnTheSnow 修复）
```

## 第 3 步：切换 Lambda 到 Supabase

1. Supabase Dashboard（Prod）→ **Connect** → **Transaction pooler**（端口 6543）复制连接串，
   在末尾加 `?sslmode=require`，写进 `terraform/terraform.tfvars`（已 gitignore）：
   ```hcl
   database_url = "postgresql://postgres.jbucqclsoqcjvnefiyyw:<密码>@aws-0-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require"
   ```
2. 刷新 AWS 凭证后：
   ```bash
   cd terraform
   terraform plan \
     -target=aws_lambda_function.api -target=aws_lambda_function.collector \
     -target=aws_lambda_function.contact_collector -target=aws_lambda_function.trails_collector \
     -target=aws_lambda_function.snow_checker
   terraform apply <同样的 -target>
   ```
   plan 里应只看到这 5 个函数的 `vpc_config` 置空、环境变量替换。
   ⚠️ terraform 会整体替换环境变量，`deploy.yml` 合并进去的 `OPENMETEO_API_KEY`、
   `SUPABASE_*`、`ADMIN_API_KEY`、`GOOGLE_MAPS_API_KEY` 会被清掉 → 下一步补回。
3. GitHub Actions → *deploy* → **Re-run all jobs**（把上面那几个变量重新合并进去）

## 第 4 步：验证

```bash
aws lambda invoke --function-name resort-data-collector --payload '{}' /tmp/collector.json && cat /tmp/collector.json
curl -s https://api.steponsnow.com/api/status
curl -s https://api.steponsnow.com/api/resorts/2 | head -c 600
```
- Supabase Prod：`resort_conditions` / `resort_weather` 约 262 行、`resort_webcams` 约 860 行，timestamp 为刚才
- App（Release 版）雪场列表 / 详情 / 天气 / 摄像头正常
- CloudWatch：api 日志里是 `数据库: aws-0-us-west-2.pooler.supabase.com (Supabase pooler, NullPool)`、`Redis 缓存: 未启用`

## 第 5 步：观察 1–2 天后下线 AWS 资源

1. RDS 打最终快照（`aws rds create-db-snapshot ...`），确认快照 available
2. terraform 删除 `rds.tf`、`elasticache.tf`、NAT Gateway / EIP（`vpc.tf`）及只给它们用的安全组，
   `terraform plan` 逐项确认后 apply
3. 账单下个周期确认 NAT / RDS / ElastiCache 归零

## 回滚

第 3 步之后出问题：`git revert` terraform 改动并 `terraform apply` 同样的 `-target`，
Lambda 回到 VPC + RDS（第 5 步之前 RDS 一直在）。
