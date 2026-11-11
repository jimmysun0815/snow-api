#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送 Lambda（resort-data-sqs-notification-processor / resort-data-prod-notification-processor）

调用方式：
  1. Lambda Function URL —— Supabase 的 enqueue_push() / push_outbox_retry_due() 通过 pg_net POST
     body: {"type":"INSERT","table":"push_outbox","record":{"id":..,"user_id":..,...}}
  2. SQS Event Source Mapping —— 兼容保留（record 格式同上，不带 id）
  3. 直接 invoke —— 本地/控制台测试，event 就是 record

push_outbox 状态流转（id 存在时）：
  push_outbox_claim(id)  pending|failed → sending   （认领失败 = 已被处理，直接返回）
  发送完成后 push_outbox_mark(id, status, error, detail)（detail = 设备数 / 成功 / 失效 / 可重试，迁移 159）：
    sent    —— 至少一台设备成功
    skipped —— 没有设备 / 全部 token 失效（重试也没用）
    failed  —— 只有临时错误，数据库按退避重试（最多 5 次）

HTTP 永远返回 200（除非请求本身不合法）：结果已经写回 push_outbox，
pg_net 不会根据状态码重试，返回 500 只会制造噪音日志。
"""

import base64

import requests
import json
from typing import Any, Dict, Optional, Tuple

from push_service import healthcheck, send_to_users, sb_rpc

# Firebase 不在模块加载时初始化：凭证配置错误时整个 Lambda 会在 INIT 阶段崩溃，
# 什么都记不下来。改为发送时（send_to_users 内部）惰性初始化，失败会作为
# 可重试错误写进 push_outbox.last_error，凭证修好后由重试任务自动补发。


def _response(status: int, payload: Dict) -> Dict[str, Any]:
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(payload, ensure_ascii=False),
    }


# =====================================================
# 核心处理
# =====================================================

def process_notification(record: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[Dict]]:
    """
    发送一条通知。返回 (status, error)，status ∈ sent | skipped | failed。
    """
    user_id = record.get('user_id')
    if not user_id:
        return 'skipped', 'missing user_id', None

    data = record.get('data') or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {}

    notification_type = record.get('notification_type')
    print(f"🔔 处理通知: user={user_id}, type={notification_type}")

    try:
        result = send_to_users(
            user_ids=[user_id],
            title=record.get('title') or '',
            body=record.get('body') or '',
            data=data,
            notification_type=notification_type,
            image_url=record.get('image_url'),
        )
    except Exception as e:                 # 查 token / Firebase 鉴权等异常 → 可重试
        print(f"❌ 发送异常: {e}")
        return 'failed', f'{type(e).__name__}: {e}', None

    detail = {k: result[k] for k in ('device_count', 'success_count', 'invalid_count', 'retryable_count')}
    if result['device_count'] == 0:
        return 'skipped', 'no devices', detail
    if result['success_count'] > 0:
        return 'sent', None, detail
    if result['retryable_count'] > 0:
        return 'failed', '; '.join(result['errors'])[:1000] or 'retryable error', detail
    return 'skipped', 'all tokens invalid', detail


def _mark(outbox_id, status, error, detail):
    """回写结果；迁移 159 之前 push_outbox_mark 没有 p_detail 参数（404），退回 3 参数调用。"""
    try:
        sb_rpc('push_outbox_mark', {'p_id': outbox_id, 'p_status': status, 'p_error': error, 'p_detail': detail})
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 404:
            raise
        sb_rpc('push_outbox_mark', {'p_id': outbox_id, 'p_status': status, 'p_error': error})


def process_outbox_record(record: Dict[str, Any]) -> str:
    """带 outbox id 的记录：认领 → 发送 → 回写。返回最终状态（或 'already_handled'）。"""
    outbox_id = record.get('id')
    if outbox_id is None:
        status, _, _ = process_notification(record)
        return status

    try:
        claimed = sb_rpc('push_outbox_claim', {'p_id': outbox_id})
    except Exception as e:
        # 认领失败（Supabase 暂时不可用）→ 不发送，让重试任务稍后再投
        print(f"❌ 认领 outbox {outbox_id} 失败: {e}")
        return 'claim_error'
    if not claimed:
        print(f"ℹ️  outbox {outbox_id} 已被处理，跳过")
        return 'already_handled'

    status, error, detail = process_notification(record)
    try:
        _mark(outbox_id, status, error, detail)
    except Exception as e:
        # 回写失败：行停在 sending，5 分钟后会被重投（可能重复一次，好过丢失）
        print(f"❌ 回写 outbox {outbox_id} 状态失败: {e}")
    print(f"✅ outbox {outbox_id} → {status}" + (f" ({error})" if error else ''))
    return status


# =====================================================
# 入口
# =====================================================

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    if event.get('action') == 'healthcheck':
        return _response(200, healthcheck())
    if 'Records' in event:
        return handle_sqs_batch(event)
    if 'body' in event and 'headers' in event:
        return handle_http_request(event)
    # 直接 invoke（测试）：event 可以是信封也可以是 record
    record = event.get('record', event)
    status = process_outbox_record(record)
    return _response(200, {'status': status})


def handle_http_request(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        body_str = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            body_str = base64.b64decode(body_str).decode('utf-8')
        payload = json.loads(body_str)
    except (ValueError, TypeError) as e:
        print(f"⚠️  请求体不是合法 JSON: {e}")
        return _response(400, {'error': 'invalid json'})

    if payload.get('type') != 'INSERT' or not isinstance(payload.get('record'), dict):
        print(f"⚠️  未知的 webhook 格式: type={payload.get('type')}")
        return _response(400, {'error': 'unknown webhook payload'})

    record = payload['record']
    # 旧版触发器（table=push_notification_queue）不带 outbox id，直接发送
    if payload.get('table') != 'push_outbox':
        record = {k: v for k, v in record.items() if k != 'id'}

    try:
        status = process_outbox_record(record)
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        status = 'error'
    return _response(200, {'status': status})


def handle_sqs_batch(event: Dict[str, Any]) -> Dict[str, Any]:
    failures = []
    for rec in event['Records']:
        message_id = rec.get('messageId')
        try:
            body = json.loads(rec['body'])
        except (ValueError, KeyError) as e:
            print(f"❌ SQS 消息 {message_id} 无法解析，丢弃: {e}")
            continue
        record = body.get('record', body)
        try:
            status = process_outbox_record(record)
        except Exception as e:
            print(f"❌ SQS 消息 {message_id} 处理异常: {e}")
            status = 'failed'
        if status in ('failed', 'claim_error') and record.get('id') is None:
            failures.append({'itemIdentifier': message_id})   # 无 outbox 时交给 SQS 重试
    return {'batchItemFailures': failures}


if __name__ == '__main__':
    print(lambda_handler({
        'user_id': 'test-user-uuid',
        'notification_type': 'test',
        'title': '测试通知',
        'body': '这是一条测试消息',
        'data': {'type': 'test'},
    }, None))
