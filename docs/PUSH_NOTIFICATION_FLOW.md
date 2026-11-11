# 推送通知链路（2026-11 改造后）

## 总览

```
业务表 INSERT/UPDATE（消息、拼车、网球…）
  └─ 触发器 / RPC  ──►  public.enqueue_push(payload)
                          ├─ INSERT push_outbox (status=pending)
                          └─ pg_net POST ──► 推送 Lambda（Function URL）
                                              ├─ push_outbox_claim(id)   pending|failed → sending
                                              ├─ 查 device_tokens（含 locale）+ push_badge_counts
                                              ├─ FCM send_each（按设备语言渲染文案、角标=未读数）
                                              ├─ 删除失效 token
                                              └─ push_outbox_mark(id, sent|skipped|failed)

pg_cron「push-outbox-retry」每分钟：
  到期的 pending（快速投递丢了 / Lambda 429）、卡住的 sending、到期的 failed  ──►  重新 POST
  认领最多 5 次 / 重投最多 8 次后 → dead
```

降雪提醒（`check_snow_and_notify.py`，EventBridge 每小时）直接调用 `push_service.send_snow_alert_notification`，不经过 outbox。

## 代码位置

| 作用 | 位置 |
|------|------|
| outbox / 重试 / RPC / device_tokens 变更 | app 仓库 `supabase/migrations/155_push_outbox.sql` |
| webhook URL（每个环境一行） | `app_settings.push_webhook_url`（154，取值见 app 仓库 `supabase/env/README.md`） |
| 触发器改用 enqueue_push | `156_push_triggers_use_outbox.sql` |
| Lambda 入口 | `sqs_notification_processor.py` |
| 查 token / 渲染 / 发送 | `push_service.py` |
| 降雪提醒 | `check_snow_and_notify.py` |
| App 端 | app 仓库 `lib/services/push_notification_service.dart` |
| 离线单元测试 | `tests/test_push_service.py` |

## push_outbox 状态

| status | 含义 | 后续 |
|--------|------|------|
| pending | 已入队，等待 Lambda 认领 | 2 分钟没被认领 → 重试任务重投 |
| sending | Lambda 已认领 | 5 分钟没回写 → 视为卡死重投 |
| sent | 至少一台设备成功 | 终态，14 天后清理 |
| skipped | 用户没有设备 / token 全部失效 | 终态 |
| failed | 只有临时错误（FCM 不可用、网络） | 1/2/4/8 分钟后重试 |
| dead | 超过重试上限 | 终态，看 `last_error` 排查 |

排查常用：

```sql
SELECT status, count(*) FROM push_outbox WHERE created_at > now() - interval '1 day' GROUP BY 1;
SELECT id, user_id, notification_type, attempts, posts, last_error
  FROM push_outbox WHERE status IN ('failed','dead') ORDER BY id DESC LIMIT 50;
```

## 多语言

触发器写入的 title / body 是中文。`device_tokens.locale = 'en'` 的设备由 `push_service.render_for_locale`
按 `data.template_key`（或 `data.type` → 模板映射，与迁移 144 一致）渲染英文，文案对齐 App 的
`app_en.arb`。私信（type=message）标题是发送者昵称、正文是消息原文，不做翻译。
App 切换语言时会重新注册 token，更新 locale。

## 设备 token

- `token` 全局唯一；App 通过 RPC `register_device_token(p_token, p_platform, p_locale)` 注册，
  同一台手机换账号登录时 token 自动转给新账号。
- 目前仍保留 `(user_id, platform)` 唯一约束以兼容旧版 App；执行 `157_device_tokens_multi_device.sql`
  后同一用户可以多台设备同时收推送。

## 部署顺序

Prod 上线的完整步骤、验证和回滚见 [`PROD_PUSH_ROLLOUT.md`](PROD_PUSH_ROLLOUT.md)。要点：先部署 Lambda，再执行 155 / 156，
雪况推送用 `app_settings.snow_push_enabled` 做闸门。部署后用 `scripts/verify_push_deploy.sh dev|prod` 做只读检查。

## 已知未处理（P0，单独排期）

- Lambda Function URL 没有鉴权：任何人拿到 URL 都能伪造推送。建议在 `app_settings` 加一个共享密钥，
  `_push_outbox_post` 带上请求头，Lambda 校验。
- 退出登录时没有删除本机 token（换账号登录时已由 `register_device_token` 自动纠正，但登出后到下次登录之间，
  旧账号的推送仍会到达这台设备）。
