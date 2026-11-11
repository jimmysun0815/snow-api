#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snow Alert Checker
Checks for upcoming snow and sends push notifications.

Data sources:
  - Supabase (REST API): resort_subscriptions, resorts (name), snow_notification_logs, device_tokens
  - RDS (psycopg2): resort_weather.forecast_7d (weather forecast data)
"""

import os
import json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from push_service import send_snow_alert_notification, supabase_auth_headers


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
    雪况推送总开关（夏季雪况数据源退订后关闭，冬季再打开）。

    判定优先级:
      1. 环境变量 SNOW_PUSH_ENABLED=true/false —— 运维强制开关，设了就听它的
      2. Supabase 未配置（缺 SUPABASE_URL/SUPABASE_SERVICE_KEY）—— 视为关闭，
         因为没有订阅数据推送本来就无法工作
      3. Supabase app_settings 表 key='snow_push_enabled' —— App 管理界面可调
      4. 都没有 → 默认开启

    冬季重新启用步骤: 给本 Lambda 配置 SUPABASE_URL + SUPABASE_SERVICE_KEY
    环境变量（并确保 app_settings 里没有 snow_push_enabled=false 的行）。
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
        if rows:
            value = rows[0].get('value')
            if isinstance(value, str):  # JSONB 里存了字符串 "false" 的情况
                return value.strip().lower() not in ('false', '0', 'no')
            return bool(value)
    except Exception as e:
        print(f"[WARN] 读取 app_settings.snow_push_enabled 失败，按开启处理: {e}")

    return True


PAGE_SIZE = 1000   # PostgREST 默认单次最多返回 1000 行，超出部分会被静默截断，所以要分页


def _get_active_subscriptions():
    """
    Fetch all active resort subscriptions from Supabase, with resort name.

    不用 PostgREST 关联查询 resorts(name)：Prod 的 resort_subscriptions.resort_id 没有指向
    resorts 的外键（订阅表比 151 迁过来的 resorts 表早），关联查询会返回 400。
    改为两步：分页查订阅，再按 resort_id 分批查名字。返回形状不变：
    [{'resort_id', 'user_id', 'resorts': {'name'} | None}]
    """
    url = f'{_supabase_url()}/rest/v1/resort_subscriptions'
    subs, offset = [], 0
    while True:
        params = {
            'is_active': 'eq.true',
            'select': 'id,resort_id,user_id',
            'order': 'id',
            'limit': str(PAGE_SIZE),
            'offset': str(offset),
        }
        response = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
        response.raise_for_status()
        page = response.json()
        subs.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    names = {}
    resort_ids = sorted({s['resort_id'] for s in subs})
    for i in range(0, len(resort_ids), 200):
        chunk = resort_ids[i:i + 200]
        response = requests.get(
            f'{_supabase_url()}/rest/v1/resorts',
            headers=_supabase_headers(),
            params={'id': f'in.({",".join(str(r) for r in chunk)})', 'select': 'id,name'},
            timeout=10,
        )
        response.raise_for_status()
        names.update({r['id']: r['name'] for r in response.json()})

    return [
        {
            'resort_id': s['resort_id'],
            'user_id': s['user_id'],
            'resorts': {'name': names[s['resort_id']]} if s['resort_id'] in names else None,
        }
        for s in subs
    ]


def _check_already_notified(resort_id, forecast_date):
    """
    这个雪场的这个降雪日是否已经提醒过。

    以前去重键带 notification_date（=今天），同一个降雪日会在提前 3 / 2 / 1 天
    各推一次；现在同一个 (雪场, 降雪日) 只推一次。
    """
    url = f'{_supabase_url()}/rest/v1/snow_notification_logs'
    params = {
        'resort_id': f'eq.{resort_id}',
        'forecast_date': f'eq.{forecast_date}',
        'select': 'id',
        'limit': '1',
    }
    response = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
    response.raise_for_status()
    return len(response.json()) > 0


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


def check_snow_alerts(dry_run=False):
    """Check for snow alerts and send push notifications.

    dry_run=True：完整计算会提醒哪些雪场 / 多少用户，但不写日志、不发送。
    返回 [{'resort_id','resort','snow_date','snowfall_cm','users'}]（实际发送 / 将要发送的列表）。

    1. Read active subscriptions from Supabase
    2. Read latest weather forecast from RDS (resort_weather.forecast_7d)
    3. If snowfall >= 3cm in next 3 days and not yet notified today, send push
    4. Log notification to Supabase for deduplication
    """
    # --- Step 1: Get active subscriptions from Supabase ---
    raw_subscriptions = _get_active_subscriptions()
    print(f"Found {len(raw_subscriptions)} active subscriptions")

    if not raw_subscriptions:
        print("No active subscriptions, exiting")
        return []

    # Group by resort_id
    resort_subscribers = {}
    for sub in raw_subscriptions:
        resort_id = sub['resort_id']
        resort_name = sub.get('resorts', {}).get('name', f'Resort {resort_id}') if sub.get('resorts') else f'Resort {resort_id}'
        if resort_id not in resort_subscribers:
            resort_subscribers[resort_id] = {
                'name': resort_name,
                'users': []
            }
        if sub['user_id'] not in resort_subscribers[resort_id]['users']:   # 重复订阅只算一次
            resort_subscribers[resort_id]['users'].append(sub['user_id'])

    print(f"Grouped into {len(resort_subscribers)} resorts")

    # --- Step 2: Connect to RDS for weather data ---
    # 2026-11 起数据库在 Supabase（DATABASE_URL = pooler 连接串）；
    # 没设 DATABASE_URL 时保留旧的 DB_* 变量，兼容本地调试
    if os.environ.get('DATABASE_URL'):
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
    else:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
        )

    today = datetime.now().date()
    today_str = today.isoformat()
    notifications_sent = 0
    planned = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for resort_id, info in resort_subscribers.items():
                try:
                    # Get the latest weather forecast from resort_weather table
                    cur.execute("""
                        SELECT forecast_7d
                        FROM resort_weather
                        WHERE resort_id = %s
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (resort_id,))

                    result = cur.fetchone()
                    if not result or not result['forecast_7d']:
                        print(f"No weather data for resort {resort_id} ({info['name']}), skipping")
                        continue

                    # forecast_7d is directly a JSON array of daily forecasts
                    forecast = result['forecast_7d']
                    if not isinstance(forecast, list):
                        print(f"Unexpected forecast format for resort {resort_id}, skipping")
                        continue

                    # Scan next 3 days for significant snowfall
                    for day in forecast:
                        try:
                            day_date_str = day.get('date', '')
                            if not day_date_str:
                                continue
                            forecast_date = datetime.fromisoformat(day_date_str.split('T')[0]).date()
                        except (ValueError, TypeError):
                            continue

                        days_ahead = (forecast_date - today).days
                        if days_ahead < 1 or days_ahead > 3:
                            continue

                        snowfall = day.get('snowfall') or 0
                        if snowfall < 3:
                            continue

                        # Found significant snowfall — check dedup via Supabase
                        forecast_date_str = forecast_date.isoformat()

                        if _check_already_notified(resort_id, forecast_date_str):
                            print(f"Already notified for {info['name']} snow day {forecast_date_str}, skipping")
                            continue

                        planned.append({
                            'resort_id': resort_id,
                            'resort': info['name'],
                            'snow_date': forecast_date_str,
                            'snowfall_cm': snowfall,
                            'users': len(info['users']),
                        })
                        if dry_run:
                            print(f"[DRY RUN] would notify {len(info['users'])} users: "
                                  f"{info['name']} {snowfall}cm on {forecast_date_str}")
                            break

                        title = f"{info['name']} 降雪预报 ❄️"
                        body = f"{forecast_date.month:02d}月{forecast_date.day:02d}日 预计降雪 {snowfall}cm"

                        # 先写日志再发送：如果发送途中 Lambda 超时，下一小时不会重复推送
                        # （宁可这一次漏推，也不要每小时重复轰炸）
                        try:
                            new_users = _log_notifications(
                                user_ids=info['users'],
                                resort_id=resort_id,
                                notification_date=today_str,
                                forecast_date=forecast_date_str,
                                snow_amount=snowfall,
                                weather_code=day.get('weather_code'),
                                title=title,
                                body=body,
                            )
                        except Exception as log_err:
                            print(f"Failed to write notification logs for {info['name']}, skip sending: {log_err}")
                            break

                        if not new_users:
                            print(f"All {len(info['users'])} users of {info['name']} already notified today, skip")
                            break

                        print(f"Sending snow alert for {info['name']} to {len(new_users)} users: "
                              f"{snowfall}cm on {forecast_date}")
                        result = send_snow_alert_notification(
                            user_ids=new_users,
                            resort_name=info['name'],
                            snow_date=forecast_date,
                            snow_amount=snowfall,
                            resort_id=resort_id,
                        )
                        print(f"Snow alert result for {info['name']}: {result}")

                        notifications_sent += 1
                        print(f"Notified {len(new_users)} users for {info['name']}")

                        # Only notify once per resort per run (the earliest snow day found)
                        break

                except Exception as e:
                    print(f"Error checking resort {resort_id} ({info['name']}): {e}")
                    continue

    finally:
        conn.close()

    print(f"Done. Sent {notifications_sent} snow alert(s)" + (" [DRY RUN]" if dry_run else ""))
    return planned


def lambda_handler(event, context):
    """
    Lambda handler for snow alert checking

    event {"dry_run": true}：上线 / 排查用。忽略开关，只计算会提醒谁，不写日志、不发送。
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

        # Firebase 在真正发送时（push_service.send_to_users 内部）才初始化，
        # 凭证有问题不会让整次检查直接失败
        planned = check_snow_alerts(dry_run=dry_run) or []

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Snow alerts dry run' if dry_run else 'Snow alerts checked successfully',
                'push_enabled': enabled,
                'alerts': planned,
            }, ensure_ascii=False)
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
    # Test locally
    result = lambda_handler({}, {})
    print(result)
