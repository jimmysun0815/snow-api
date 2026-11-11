# 推送改造 + 雪况推送 Prod 上线手册（2026-11）

涉及两个仓库的 `fix/push-p1-p2` 分支：

- **snow-api**（本仓库）：推送 Lambda、snow-checker、`deploy.yml`、terraform
- **snow-app**：迁移 155 / 156 / 157（以及以后的 158）、执行脚本、App 端推送代码

Dev 已于 2026-11-08 至 11-11 全部验证：数据库 155 / 156 / 157、推送 Lambda、真机私信推送、本地雪况测试推送。

## 数据保证

- 业务数据（用户、帖子、私信、通知、订阅等）：这次没有任何语句删除或修改它们。
- `device_tokens`：**只移不删**。去重（155）、换账号 / 同平台被挤掉（157 触发器 / RPC）、FCM 判定失效（Lambda 调用
  `retire_device_tokens`）的行，一律先移到 `device_tokens_backup_155`，需要时可以用回滚脚本原样放回。
- 执行前，`backup_20261108` schema 里还有一份 `device_tokens` 全表、18 个函数的原定义和 cron 任务的备份。
- 唯一会被自动清理的是新建的 `push_outbox`：已结束的行 14 天后删除。它是这次新加的投递记录，不是用户数据。
- 新版 App 还没发布时，旧版 App 的保存 token、收推送都照常工作（157 让旧版 App 换账号登录时 token 也能正确转给新账号）。


---

## 0. 上线前（Prod SQL Editor，约 1 分钟）

先把雪况推送关上，作为闸门。否则后端一部署，snow-checker 下一个整点就会开始真实推送，来不及先看 dry-run。

```sql
INSERT INTO public.app_settings (key, value) VALUES ('snow_push_enabled', 'false'::jsonb)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();

-- 顺便确认推送地址已配置（应为 https://adomdpiac62f33ihgj7lbnmlzu0xcagr.lambda-url…）
SELECT public._push_webhook_url();
```

⚠️ 在 snow-api 合并之前，不要在任何分支上运行 `terraform apply`。修复（推送 Lambda 的 `ignore_changes`）只在本分支上；
在其他分支上运行会再次把推送 Lambda 的凭证覆盖成 tfvars 里的旧值。

## 1. 合并 snow-api 的 PR → 自动部署

合并后 `deploy.yml` 会：

- 部署 Dev / Prod 推送 Lambda、snow-checker、API Lambda
- 用 GitHub Secrets 整体重写它们的环境变量（snow-checker 新增了 `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`，取自 `PROD_SUPABASE_*`）

等 GitHub Actions 成功后：

```bash
cd backend-api
AWS_PROFILE=pp ./scripts/verify_push_deploy.sh prod
AWS_PROFILE=pp ./scripts/verify_push_deploy.sh dev
```

通过的标准：

- 推送 Lambda 的环境变量齐全，健康检查里 `supabase` 和 `firebase` 都是 `ok`（`retire_rpc` 在 157 执行前会显示 missing，属于正常）
- snow-checker 的环境变量齐全，dry_run 的 `push_enabled=false`（第 0 步关掉的），并列出「现在跑的话会提醒哪些雪场 / 多少人」

新 Lambda 兼容旧格式的 payload，所以这一步完成后、155 执行前，Prod 推送照常工作。

## 2. Prod 数据库执行 155 / 156 / 157

```bash
cd app/snow_resort_app
./supabase/scripts/apply_push_migrations.sh prod
```

脚本在临时目录 link Prod，不会改动主目录的 link。流程如下：

1. 拉取远端迁移历史
2. dry-run，确认待执行的只有 155 / 156 / 157
3. 要求输入 `prod` 确认
4. 执行，每一步都有检查：
   - 前置检查：`push_webhook_url` 必须是 Prod 的地址；18 个函数必须与 154 逐字一致。任何一项不通过就中止，此时没有做任何改动。脚本还会打印 `snow_push_enabled` 的当前值。
   - 库内备份到 `backup_20261108`
   - 校验：device_tokens 行数守恒、没有函数直接调用 Lambda、权限 / owner / cron 正确。任何一项不通过就回滚该文件。
   - 冒烟测试：随机 user_id 入队
   - 157 自检：在子事务里模拟「旧版 App 在别人登录过的手机上登录」，验证 token 转给新账号、旧行进了备份表，然后回滚这个子事务，不留痕迹

然后到 CloudWatch `/aws/lambda/resort-data-prod-notification-processor` 确认出现 `outbox N → skipped (no devices)`，
再用真机发一条私信确认能收到。

## 3. 打开雪况推送

确认第 1 步 dry_run 列出的雪场和人数合理之后：

```sql
UPDATE public.app_settings SET value = 'true'::jsonb, updated_at = now() WHERE key = 'snow_push_enabled';
```

下一个整点 snow-checker 会真实发送。之后到 `/aws/lambda/resort-data-snow-checker` 看 `Snow alert result` 这一行。
同一个 (雪场, 降雪日) 只推一次，日志先写后发，不会每小时重复推。

## 4. 发布 App 新版本

合并 snow-app 的 PR，打 Release 包（Release 构建连 Prod）提交审核。新版本：

- 用 `register_device_token` 注册 token（带语言）。如果后端还没执行 155，会自动回退到旧的 upsert。
- 启动时不再直接弹系统权限框，改为先显示说明弹窗
- 回到前台时清除 iOS 角标

旧版本 App 不升级也能继续收推送。

## 5. 以后：158（多设备推送）

新版本普及后，再执行 `158_device_tokens_multi_device.sql`。在此之前，一个账号在每个平台上只有最后登录的那台设备能收到推送。

---

## 第二批（2026-11-11）：雪况只推已开放雪场 + 推送监控

起因：第一次 dry_run 列出的 25 个雪场都还没开放。

1. **Prod 数据库执行 159 / 160**：`./supabase/scripts/apply_push_migrations.sh prod`
   - 159：push_outbox 记录来源 / 触发人 / 原因 / 发送结果，保留 90 天，`push_stats`
   - 160：`snow_alert_candidates()`，新增「雪场必须开放（最新雪况 open / partial 且 72 小时内采集）」
   - 旧 Lambda、旧 snow-checker 都兼容，所以可以先执行
2. **合并 snow-api 的 PR #9**：snow-checker 改用 `snow_alert_candidates()` 判断，经 push_outbox 发送（带原因，可在后台查到）；
   读取开关失败时按关闭处理；推送 Lambda 回写发送结果
3. **合并 admin 的「推送监控」PR**：后台新增「推送监控」页（统计 / 推送记录 / 即将发送），并修复系统设置页开关总显示「关」的 bug
4. `AWS_PROFILE=pp ./scripts/verify_push_deploy.sh prod`：dry_run 会分别列出「将发送」和「跳过（原因）」
5. 在后台「推送监控 → 即将发送」确认名单后，在「系统设置」打开雪况推送

## 回滚

| 出问题的环节 | 怎么回滚 | 生效时间 |
|---|---|---|
| 雪况推送发得不对 | `UPDATE app_settings SET value='false'::jsonb WHERE key='snow_push_enabled';` | 下一个整点 |
| 155 / 156 / 157 | Prod SQL Editor 执行 app 仓库 `supabase/scripts/rollback_155_156.sql`：从备份恢复 18 个函数、撤掉 157 触发器、停掉重试任务、把备份表里的 token 放回原表 | 立即 |
| Lambda 代码 | 在 main 上 revert 这次合并 → `deploy.yml` 重新部署旧代码（注意：旧代码对 Prod 新格式的 `sb_secret_` key 可能返回 401） | 部署完成后 |
| App | 无需回滚（新旧版本都兼容） | — |

## 本次没有处理（原有的 P0，建议尽快排期）

- 推送 Lambda 的 Function URL 鉴权是 `NONE`（已确认），任何人拿到 URL 都能给任意用户伪造推送。
- 退出登录时没有删除本机 token。在下次有人登录之前，旧账号的推送仍会发到这台设备。
