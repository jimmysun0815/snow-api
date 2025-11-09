#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知处理器 - 支持两种调用方式：
1. SQS Event Source Mapping（批量处理）
2. Lambda Function URL（Supabase Webhook 直接调用）
"""

import os
import json
from typing import Dict, Any, List
from push_service import (
    send_push_notification,
    get_user_tokens,
    initialize_firebase
)

# 初始化 Firebase
initialize_firebase()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 入口函数 - 支持多种触发方式
    """
    print(f"📨 收到事件: {json.dumps(event, default=str)[:200]}...")
    
    # 判断事件类型
    if 'Records' in event:
        # SQS 批量事件
        return handle_sqs_batch(event, context)
    elif 'type' in event and event['type'] == 'INSERT':
        # Supabase Webhook
        return handle_supabase_webhook(event, context)
    else:
        # 直接调用（测试）
        return handle_direct_call(event, context)


def handle_sqs_batch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """处理 SQS 批量消息"""
    print(f"📦 处理 SQS 批量消息: {len(event['Records'])} 条")
    
    failed_messages = []
    success_count = 0
    
    for record in event['Records']:
        message_id = record['messageId']
        
        try:
            body = json.loads(record['body'])
            if process_notification(body):
                success_count += 1
            else:
                failed_messages.append({"itemIdentifier": message_id})
        except Exception as e:
            print(f"❌ 处理消息 {message_id} 失败: {e}")
            failed_messages.append({"itemIdentifier": message_id})
    
    return {
        "batchItemFailures": failed_messages
    }


def handle_supabase_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """处理 Supabase Webhook"""
    print(f"🔔 处理 Supabase Webhook")
    
    try:
        # Supabase webhook 格式
        record = event.get('record', {})
        
        notification_data = {
            'user_id': record.get('user_id'),
            'notification_type': record.get('notification_type'),
            'title': record.get('title'),
            'body': record.get('body'),
            'data': record.get('data', {})
        }
        
        success = process_notification(notification_data)
        
        return {
            'statusCode': 200 if success else 500,
            'body': json.dumps({
                'success': success,
                'message': 'Notification processed'
            })
        }
    except Exception as e:
        print(f"❌ 处理 webhook 失败: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def handle_direct_call(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """处理直接调用（测试用）"""
    print(f"🧪 处理直接调用")
    
    try:
        success = process_notification(event)
        return {
            'statusCode': 200 if success else 500,
            'body': json.dumps({
                'success': success,
                'message': 'Notification processed'
            })
        }
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_notification(data: Dict[str, Any]) -> bool:
    """
    处理单个通知
    
    Args:
        data: 通知数据
            - user_id: 用户ID
            - notification_type: 通知类型
            - title: 标题
            - body: 内容
            - data: 额外数据
    
    Returns:
        是否成功
    """
    user_id = data.get('user_id')
    notification_type = data.get('notification_type')
    title = data.get('title')
    body = data.get('body')
    extra_data = data.get('data', {})
    
    print(f"🔔 处理通知: user={user_id}, type={notification_type}, title={title}")
    
    # 获取用户 FCM tokens
    tokens = get_user_tokens(user_id)
    
    if not tokens:
        print(f"⚠️  用户 {user_id} 没有 FCM token")
        return True  # 不算失败
    
    print(f"📱 找到 {len(tokens)} 个设备")
    
    # 发送推送
    result = send_push_notification(
        tokens=tokens,
        title=title,
        body=body,
        data=extra_data
    )
    
    sent = result.get('success_count', 0)
    failed = result.get('failure_count', 0)
    
    print(f"✅ 成功 {sent} 条，失败 {failed} 条")
    
    return sent > 0


# 本地测试
if __name__ == '__main__':
    # 测试 Supabase webhook 格式
    test_event = {
        "type": "INSERT",
        "table": "push_notification_queue",
        "record": {
            "user_id": "test-user-uuid",
            "notification_type": "test",
            "title": "测试通知",
            "body": "这是一条测试消息",
            "data": {"type": "test"}
        },
        "schema": "public"
    }
    
    class MockContext:
        function_name = "test"
        aws_request_id = "test-request"
    
    result = lambda_handler(test_event, MockContext())
    print(f"\n测试结果: {result}")
