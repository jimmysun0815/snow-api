#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snow Alert Checker（EventBridge 每小时）

「该不该发」全部由数据库函数 snow_alert_candidates()（迁移 160）判断，admin「推送监控 → 即将发送」
调用的是同一个函数，所以后台看到的待发名单和这里实际发送的一致：
  - 订阅了该雪场、未来 1~3 天（UTC 日期）有 ≥3cm 降雪
  - 同一 (雪场, 降雪日) 只提醒一次
  - 雪场最新雪况为 open / partial，且是 72 小时内采集的（未开放的雪场不发）

发送：先写 snow_notification_logs（每人每雪场每天最多一条，已存在的跳过），
再经 push_outbox 入队（迁移 159），由推送 Lambda 投递 —— 自动重试、按设备语言渲染，
admin 里能查到来源（snow-checker）和原因。入队不可用时退回直接发送。

event {"dry_run": true}：忽略开关，只返回每个雪场的判断结果，不写日志、不发送。
"""

import os
import json
from datetime import datetime, timezone

import requests
from push_service import (
    enqueue_snow_alert,
    send_snow_alert_notification,
    supabase_auth_headers,
)


def _supabase_headers():
    """Return headers for Supabase REST API calls."""
    headers = supabase_auth_headers(os.environ.get('SUPABASE_SERVICE_KEY'))
    headers.update({
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    })
    return headers


def _supabase_url():
    return os.environ.get('SUPABASE_URL')


def _is_snow_push_enabled():
    """
    雪况推送总开关。

    判定优先级:
      1. 环境变量 SNOW_PUSH_ENABLED=true/false —— 运维强制开关，设了就听它的
      2. Supabase 未配置（缺 SUPABASE_URL/SUPABASE_SERVICE_KEY）—— 视为关闭
      3. Supabase app_settings 表 key='snow_push_enabled' —— admin「系统设置」可调
      4. 没有这一行 → 默认开启
      5. 读取失败 → 视为关闭（宁可这一小时不发，也不要在关闭状态下误发）
    """
    env = os.environ.get('SNOW_PUSH_ENABLED', '').strip().lower()
    if env in ('true', '1', 'yes'):
        return True
    if env in ('false', '0', 'no'):
        return False

    if not _supabase_url() or not os.environ.get('SUPABASE_SERVICE_KEY'):
        print("[SKIP] Supabase 未配置（缺 SUPABASE_URL/SUPABASE_SERVICE_KEY），雪况推送视为关闭")
        return False

    try:
        url = f'{_supabase_url()}/rest/v1/app_settings'
        params = {'key': 'eq.snow_push_enabled', 'select': 'value', 'limit': '1'}
        response = requests.get(url, headers=_supabase_headers(), params=params, timeout=5)
        response.raise_for_status()
        rows = response.json()
    except Exception as e:
        print(f"[WARN] 读取 app_settings.snow_push_enabled 失败，按关闭处理: {e}")
        return False

    if not rows:
        return True
    value = rows[0].get('value')
    if isinstance(value, str):  # JSONB 里存了字符串 "false" 的情况
        return value.strip().lower() not in ('false', '0', 'no')
    return bool(value)


def _get_candidates():
    """每个有订阅的雪场一行：action = send / skip + skip_reason（迁移 160 的 snow_alert_candidates）。"""
    response = requests.post(
        f'{_supabase_url()}/rest/v1/rpc/snow_alert_candidates',
        headers=_supabase_headers(),
        json={},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _log_notifications(user_ids, resort_id, notification_date, forecast_date,
                       snow_amount, weather_code, title, body):
    """
    批量写通知日志（一次请求），返回「这次真正新写入」的 user_id 列表。

    snow_notification_logs 有唯一约束 (user_id, resort_id, notification_date)：已存在的行跳过
    （ignore-duplicates），不会让整批失败；只给新写入的用户发送 —— 同一用户同一雪场一天最多一条。
    """
    url = f'{_supabase_url()}/rest/v1/snow_notification_logs'
    payload = [{
        'user_id': user_id,
        'resort_id': resort_id,
        'notification_date': notification_date,
        'forecast_date': forecast_date,
        'snow_amount': snow_amount,
        'weather_code': weather_code,
        'notification_title': title,
        'notification_body': body,
    } for user_id in dict.fromkeys(user_ids)]
    headers = _supabase_headers()
    headers['Prefer'] = 'return=representation,resolution=ignore-duplicates'
    response = requests.post(
        url,
        headers=headers,
        params={'on_conflict': 'user_id,resort_id,notification_date', 'select': 'user_id'},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return [r['user_id'] for r in response.json()]


def _reason(c):
    """推送监控里展示的触发原因。"""
    status = c.get('condition_status') or '未知'
    at = (c.get('condition_at') or '')[:16].replace('T', ' ')
    return (f"降雪提醒：{c['resort_name']} {c['snow_date']} 预计降雪 {c['snowfall_cm']}cm"
            f"（≥3cm，未来 3 天内）；雪场状态 {status}（{at} 采集）；该雪场订阅用户")


def _summary(c):
    """返回给调用方 / dry_run 的精简结果。"""
    return {
        'resort_id': c['resort_id'],
        'resort': c['resort_name'],
        'action': c['action'],
        'skip_reason': c.get('skip_reason'),
        'snow_date': c.get('snow_date'),
        'snowfall_cm': c.get('snowfall_cm'),
        'condition_status': c.get('condition_status'),
        'condition_at': c.get('condition_at'),
        'users': c.get('subscribers'),
    }


def check_snow_alerts(dry_run=False):
    """
    返回每个有订阅的雪场的判断结果（_summary 列表）；dry_run 时不写日志、不发送。
    """
    candidates = _get_candidates()
    to_send = [c for c in candidates if c['action'] == 'send']
    print(f"{len(candidates)} subscribed resorts, {len(to_send)} to notify"
          + (" [DRY RUN]" if dry_run else ""))
    for c in candidates:
        if c['action'] != 'send':
            print(f"  skip {c['resort_name']}: {c.get('skip_reason')}")

    results = [_summary(c) for c in candidates]
    if dry_run:
        return results

    today_str = datetime.now(timezone.utc).date().isoformat()
    for c, res in ((c, r) for c, r in zip(candidates, results) if c['action'] == 'send'):
        snow_date = datetime.fromisoformat(c['snow_date']).date()
        title = f"❄️ {c['resort_name']} 降雪预报"
        body = f"{snow_date.month:02d}月{snow_date.day:02d}日 预计降雪 {c['snowfall_cm']}cm"
        try:
            # 先写日志再发送：发送途中超时，下一小时也不会重复推
            new_users = _log_notifications(
                user_ids=c['user_ids'], resort_id=c['resort_id'],
                notification_date=today_str, forecast_date=c['snow_date'],
                snow_amount=c['snowfall_cm'], weather_code=None, title=title, body=body,
            )
        except Exception as e:
            print(f"Failed to write notification logs for {c['resort_name']}, skip sending: {e}")
            res['result'] = f'log failed: {e}'
            continue

        if not new_users:
            print(f"All users of {c['resort_name']} already notified today, skip")
            res['result'] = 'already notified today'
            continue

        queued = enqueue_snow_alert(new_users, c['resort_name'], snow_date, c['snowfall_cm'],
                                    resort_id=c['resort_id'], reason=_reason(c))
        if queued['failed']:
            print(f"enqueue failed for {len(queued['failed'])} users, sending directly")
            send_snow_alert_notification(queued['failed'], c['resort_name'], snow_date,
                                         c['snowfall_cm'], resort_id=c['resort_id'])
        res['result'] = f"queued {len(queued['queued'])}, direct {len(queued['failed'])}"
        print(f"Snow alert {c['resort_name']}: {res['result']}")

    return results


def lambda_handler(event, context):
    """
    Lambda handler for snow alert checking

    event {"dry_run": true}：上线 / 排查用。忽略开关，只返回判断结果，不写日志、不发送。
    """
    dry_run = bool((event or {}).get('dry_run'))
    try:
        enabled = _is_snow_push_enabled()
        if not enabled and not dry_run:
            print("[SKIP] 雪况推送开关关闭，跳过本次检查")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Snow push disabled, check skipped'
                })
            }

        results = check_snow_alerts(dry_run=dry_run) or []
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Snow alerts dry run' if dry_run else 'Snow alerts checked successfully',
                'push_enabled': enabled,
                'alerts': [r for r in results if r['action'] == 'send'],
                'skipped': [r for r in results if r['action'] != 'send'],
            }, ensure_ascii=False, default=str)
        }

    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


if __name__ == '__main__':
    print(lambda_handler({'dry_run': True}, {}))
