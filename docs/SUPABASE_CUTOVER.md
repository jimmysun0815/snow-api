# 雪场数据库：AWS RDS → Supabase Prod 切换手册（2026-11）

目标：5 个 Lambda（api / collector / contact-collector / trails-collector / snow-checker）
改连 Supabase Prod、移出 VPC，然后下线 RDS + ElastiCache + NAT Gateway（约 -$64/月）。

原则：**不能影响现有功能和用户**。App 本身不改代码（Release 版仍请求 `api.steponsnow.com`），
网球、社交、登录、推送都只在 Supabase，跟这次切换无关；受影响的只有雪场数据链路。

## 已完成

| 项 | 状态 |
|---|---|
| Supabase Prod schema（app 仓库 `supabase db push`，000000–000009） | ✅ 已推，和 Dev 核对一致 |
| `app_settings`（推送地址等） | ✅ Dev / Prod 都已写入 |
| 后端代码（NullPool、Redis 可选、snow-checker 读 `DATABASE_URL`、OnTheSnow 修复） | ✅ PR #3 已合并并部署（仍连 RDS） |
| sync-resorts workflow | ✅ 已删除（GitHub 上早已因不活跃停用） |
| Dev 演练：本地 API → Supabase Dev pooler，全量采集 260/261 | ✅ |

## 为什么不用 `terraform apply` 切换

- terraform 会**整体覆盖** Lambda 环境变量；线上有很多 key 不在 terraform 里
  （`SUPABASE_*`、`OPENMETEO_API_KEY`、`GOOGLE_MAPS_API_KEY`、`ADMIN_API_KEY`、`FIREBASE_*` …），
  一 apply 就没了（删除账号、雪况推送等会坏）。
- `contact_collector` 在 terraform 里是 `placeholder.zip`，apply 会把真实代码换成占位包。
- 本地 tfstate 停在 2026-03，和线上有漂移。

所以切换用 `scripts/cutover_lambdas.sh`（AWS CLI，在现有环境变量上增删，自动备份、可回滚）；
terraform 只改成和切换后的状态一致，并对这 5 个函数 `ignore_changes = [environment, 代码包]`，
以后下线 RDS 时跑 terraform 也不会碰它们。

## 第 0 步：准备（不影响线上）

1. **Prod 导入雪场**：Prod SQL Editor 执行 `resort-data/migration_export/import_resorts_to_supabase.sql`
   （RLS 提示选 *Run without RLS*），最后一行应为 `274 | 12 | 12`。
2. **Prod pooler 连接串**：Supabase Dashboard（Prod）→ Connect → Transaction pooler → **Shared pooler**
   （主机 `aws-…pooler.supabase.com`，用户名 `postgres.jbucqclsoqcjvnefiyyw`，端口 6543），末尾加 `?sslmode=require`。
   - 写进 `terraform/terraform.tfvars`：`database_url = "…"`
   - 写进 GitHub secret：`gh secret set DATABASE_URL -R jimmysun0815/snow-api`（粘贴后回车）
3. **合并「切换安全修复」PR**（deploy.yml 的 snow-checker 改用 `DATABASE_URL`）。
   必须在第 2 步 secret 配好之后合并，否则部署会在 snow-checker 那步报错退出。
   合并后会自动部署；snow-checker 此时还在 VPC 里，经 NAT 连 Supabase，没问题。
4. **AWS 凭证**：`aws sts get-caller-identity` 能返回账号 579866932024。
5. `scripts/cutover_lambdas.sh status`：确认 5 个函数都在 VPC 里（子网数 > 0）、状态 Active/Successful。

## 第 1 步：预先填充 Prod 数据（避免切换瞬间 App 看到空雪况）

Prod 的时序表现在是空的。如果先切 API 再等采集，中间几分钟 App 里雪场会没有雪况/天气。
所以先在本地把 Prod 填满（和 Dev 演练同一套代码，约 3 分钟）：

```bash
cd backend-api
DATABASE_URL="$(sed -n 's/^ *database_url *= *"\(.*\)" *$/\1/p' terraform/terraform.tfvars)" \
REDIS_URL= REDIS_HOST= \
./venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv(override=False)
from resort_manager import ResortDataManager
r = ResortDataManager(config_file='resorts_config.json').collect_all(enabled_only=True, max_workers=10)
print('DONE', len(r))"
```

（命令行里的 `DATABASE_URL` 优先于 `.env`，`.env` 不用改。）
完成后 Prod SQL Editor：`select count(*), max("timestamp") from resort_conditions;` 应约 260 行、时间为刚才。

## 第 2 步：切换

```bash
scripts/cutover_lambdas.sh switch
```

逐个函数：备份到 `.cutover_backup/` → 删 `POSTGRES_*`/`DB_*`/`REDIS_*`、加 `DATABASE_URL` → 移出 VPC。
API 放在最后。全程约 5–10 分钟（移出 VPC 每个要等 1–2 分钟），期间旧版本继续服务，不中断。

## 第 3 步：验证

```bash
curl -s https://api.steponsnow.com/api/status                 # database: connected, total_resorts: 274
curl -s https://api.steponsnow.com/api/resorts/2 | head -c 400 # last_update 为第 1 步的时间
aws lambda invoke --region us-west-2 --function-name resort-data-collector \
  --invocation-type Event /dev/null                             # 触发一次线上采集
```

- 约 5 分钟后再看 `/api/resorts/2`，`last_update` 变成线上采集的时间 → collector 写 Supabase 正常。
- CloudWatch `/aws/lambda/resort-data-api`：`数据库: aws-…pooler.supabase.com (Supabase pooler, NullPool)`、`Redis 缓存: 未启用`，无报错。
- **Release 版 App**：
  - 滑雪：雪场列表、详情（雪况/开板日期/天气/逐时预报）、摄像头、拼车/拼房里的雪场名
  - 网球 / 社交：登录、发消息（对方收到推送）、活动列表 —— 这些不走这条链路，确认没被波及即可

## 第 4 步：观察 1–2 天

- EventBridge 定时采集每次都成功（CloudWatch collector 日志）
- 每天 UTC 10:00 `cleanup-resort-timeseries` 后，时序表只保留 7 天
- snow-checker 每小时运行无报错

## 第 5 步：下线 AWS 资源（另行确认后再做）

1. **先改 admin 后台**（`snow-admin` 仓库）：编辑/删除雪场时还会写 RDS，RDS 删了会报错 → 改成只写 Supabase。
2. RDS 打最终快照：`aws rds create-db-snapshot --db-instance-identifier <id> --db-snapshot-identifier resort-data-final-2026-11`，确认 available。
3. terraform 删除 `rds.tf`、`elasticache.tf`、NAT Gateway / EIP 及只给它们用的安全组；
   先 `terraform plan`，逐项确认只有这些资源被删、5 个 Lambda 无变化，再 apply。
4. 下个账单周期确认 RDS / ElastiCache / NAT 费用归零。

## 回滚（第 5 步之前随时可用）

```bash
scripts/cutover_lambdas.sh rollback
```

按备份恢复环境变量和 VPC，Lambda 回到 RDS + Redis。RDS 在切换期间没有新数据，
回滚后下一次定时采集就会补上（雪况是「最新一条」，不影响显示）。

## 附：雪况推送开关

`deploy.yml` 每次部署会**整体重写** snow-checker 的环境变量，目前不含 `SUPABASE_URL` /
`SUPABASE_SERVICE_KEY`，按 `check_snow_and_notify.py` 的逻辑这等于「雪况推送关闭」（夏季模式）。
雪季要打开：在 deploy.yml 的 snow-checker 那段加上这两个变量（secrets 已有），合并部署即可。
