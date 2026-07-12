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
from push_service import send_snow_alert_notification, initialize_firebase


def _supabase_headers():
    """Return headers for Supabase REST API calls."""
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    return {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }


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


def _get_active_subscriptions():
    """Fetch all active resort subscriptions from Supabase, with resort name."""
    url = f'{_supabase_url()}/rest/v1/resort_subscriptions'
    params = {
        'is_active': 'eq.true',
        'select': 'resort_id,user_id,resorts(name)',
    }
    response = requests.get(url, headers=_supabase_headers(), params=params)
    response.raise_for_status()
    return response.json()


def _check_already_notified(resort_id, notification_date, forecast_date):
    """Check if we already sent a notification for this resort+date combo today via Supabase."""
    url = f'{_supabase_url()}/rest/v1/snow_notification_logs'
    params = {
        'resort_id': f'eq.{resort_id}',
        'notification_date': f'eq.{notification_date}',
        'forecast_date': f'eq.{forecast_date}',
        'select': 'id',
        'limit': '1',
    }
    response = requests.get(url, headers=_supabase_headers(), params=params)
    response.raise_for_status()
    return len(response.json()) > 0


def _log_notification(user_id, resort_id, notification_date, forecast_date,
                      snow_amount, weather_code, title, body):
    """Write a notification log entry to Supabase."""
    url = f'{_supabase_url()}/rest/v1/snow_notification_logs'
    payload = {
        'user_id': user_id,
        'resort_id': resort_id,
        'notification_date': notification_date,
        'forecast_date': forecast_date,
        'snow_amount': snow_amount,
        'weather_code': weather_code,
        'notification_title': title,
        'notification_body': body,
    }
    response = requests.post(url, headers=_supabase_headers(), json=payload)
    response.raise_for_status()


def check_snow_alerts():
    """Check for snow alerts and send push notifications.

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
        return

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
        resort_subscribers[resort_id]['users'].append(sub['user_id'])

    print(f"Grouped into {len(resort_subscribers)} resorts")

    # --- Step 2: Connect to RDS for weather data ---
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
    )

    today = datetime.now().date()
    today_str = today.isoformat()
    notifications_sent = 0

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

                        if _check_already_notified(resort_id, today_str, forecast_date_str):
                            print(f"Already notified for {info['name']} on {forecast_date_str}, skipping")
                            continue

                        # Send push notification
                        snow_date_display = forecast_date.strftime('%m月%d日')
                        print(f"Sending snow alert for {info['name']}: {snowfall}cm on {forecast_date}")

                        send_snow_alert_notification(
                            user_ids=info['users'],
                            resort_name=info['name'],
                            snow_date=snow_date_display,
                            snow_amount=snowfall
                        )

                        # Log to Supabase for each user
                        title = f"{info['name']} 降雪预报 ❄️"
                        body = f"{snow_date_display} 预计降雪 {snowfall}cm"

                        for user_id in info['users']:
                            try:
                                _log_notification(
                                    user_id=user_id,
                                    resort_id=resort_id,
                                    notification_date=today_str,
                                    forecast_date=forecast_date_str,
                                    snow_amount=snowfall,
                                    weather_code=day.get('weather_code'),
                                    title=title,
                                    body=body,
                                )
                            except Exception as log_err:
                                print(f"Failed to log notification for user {user_id}: {log_err}")

                        notifications_sent += 1
                        print(f"Notified {len(info['users'])} users for {info['name']}")

                        # Only notify once per resort per run (the earliest snow day found)
                        break

                except Exception as e:
                    print(f"Error checking resort {resort_id} ({info['name']}): {e}")
                    continue

    finally:
        conn.close()

    print(f"Done. Sent {notifications_sent} snow alert(s)")


def lambda_handler(event, context):
    """Lambda handler for snow alert checking"""
    try:
        if not _is_snow_push_enabled():
            print("[SKIP] 雪况推送开关关闭，跳过本次检查")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Snow push disabled, check skipped'
                })
            }

        initialize_firebase()
        check_snow_alerts()

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Snow alerts checked successfully'
            })
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
