#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQS Notification Processor Lambda
实时处理 SQS 队列中的推送通知请求，使用 Firebase 发送
"""

import os
import json
from typing import List, Dict, Any
from push_service import (
    send_push_notification,
    get_user_tokens,
    initialize_firebase
)

# 初始化 Firebase（在全局作用域，Lambda 容器复用时只初始化一次）
initialize_firebase()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 入口函数，处理 SQS 批次消息
    
    事件格式:
    {
        "Records": [
            {
                "messageId": "...",
                "receiptHandle": "...",
                "body": "{...}",
                "attributes": {...},
                "messageAttributes": {...}
            }
        ]
    }
    
    Args:
        event: SQS 事件，包含批次消息
        context: Lambda 上下文
    
    Returns:
        处理结果，包含失败的消息ID（用于重试）
    """
    record_count = len(event.get('Records', []))
    print(f"📨 收到 {record_count} 条 SQS 消息")
    
    failed_messages = []
    success_count = 0
    
    for record in event['Records']:
        message_id = record['messageId']
        receipt_handle = record['receiptHandle']
        
        try:
            # 解析消息体
            body = json.loads(record['body'])
            
            # 提取通知信息
            user_id = body.get('user_id')
            notification_type = body.get('notification_type')
            title = body.get('title')
            message_body = body.get('body')
            data = body.get('data', {})
            image_url = body.get('image_url')
            
            print(f"🔔 处理通知: user={user_id}, type={notification_type}, title={title}")
            
            # 获取用户的 FCM tokens
            tokens = get_user_tokens(user_id)
            
            if not tokens:
                print(f"⚠️  用户 {user_id} 没有 FCM token，跳过")
                # 这不算失败，用户可能未授权推送或未登录
                success_count += 1
                continue
            
            print(f"📱 找到 {len(tokens)} 个设备 token")
            
            # 发送推送通知（使用现有的 push_service）
            result = send_push_notification(
                tokens=tokens,
                title=title,
                body=message_body,
                data=data,
                image_url=image_url
            )
            
            sent = result.get('success_count', 0)
            failed = result.get('failure_count', 0)
            
            print(f"✅ 成功发送 {sent} 条，失败 {failed} 条")
            
            # 只要有一个成功就算成功
            if sent > 0:
                success_count += 1
            else:
                # 全部失败，标记为需要重试
                print(f"❌ 消息 {message_id} 的所有设备都发送失败")
                failed_messages.append({
                    "itemIdentifier": message_id
                })
            
        except json.JSONDecodeError as e:
            print(f"❌ 消息 {message_id} JSON 解析失败: {e}")
            # JSON 解析失败不重试，直接丢弃（可能是数据格式错误）
            success_count += 1
            
        except KeyError as e:
            print(f"❌ 消息 {message_id} 缺少必要字段: {e}")
            # 缺少字段不重试，直接丢弃
            success_count += 1
            
        except Exception as e:
            print(f"❌ 处理消息 {message_id} 失败: {e}")
            import traceback
            traceback.print_exc()
            # 其他错误标记为重试
            failed_messages.append({
                "itemIdentifier": message_id
            })
    
    # 返回处理结果
    if failed_messages:
        print(f"⚠️  {len(failed_messages)}/{record_count} 条消息处理失败，将重试")
        return {
            "batchItemFailures": failed_messages
        }
    else:
        print(f"✅ 所有 {record_count} 条消息处理成功")
        return {
            "batchItemFailures": []
        }


# 用于本地测试
if __name__ == '__main__':
    # 模拟 SQS 事件
    test_event = {
        "Records": [
            {
                "messageId": "test-message-1",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "user_id": "test-user-uuid",
                    "notification_type": "test",
                    "title": "测试通知",
                    "body": "这是一条测试消息",
                    "data": {
                        "type": "test",
                        "test_id": "123"
                    }
                }),
                "attributes": {},
                "messageAttributes": {}
            }
        ]
    }
    
    # 模拟 Lambda 上下文
    class MockContext:
        function_name = "test-function"
        memory_limit_in_mb = 512
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
        aws_request_id = "test-request-id"
    
    result = lambda_handler(test_event, MockContext())
    print(f"\n测试结果: {result}")
