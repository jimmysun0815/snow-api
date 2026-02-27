#!/usr/bin/env python3
"""
Firebase Push Notification 诊断脚本
检查 Firebase 配置和 token 有效性
"""

import os
import sys
import json
import firebase_admin
from firebase_admin import credentials, messaging

def initialize_firebase():
    """初始化 Firebase"""
    try:
        firebase_admin.get_app()
        print("✅ Firebase 已初始化")
    except ValueError:
        private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
        
        cred_dict = {
            "type": "service_account",
            "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
            "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": private_key,
            "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        }
        
        print(f"📋 Firebase Project ID: {cred_dict['project_id']}")
        print(f"📋 Client Email: {cred_dict['client_email']}")
        
        try:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase 初始化成功")
        except Exception as e:
            print(f"❌ Firebase 初始化失败: {e}")
            sys.exit(1)

def test_token(token: str, platform: str):
    """测试单个 token"""
    print(f"\n{'='*60}")
    print(f"🧪 测试 {platform} Token: {token[:20]}...")
    print(f"{'='*60}")
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title="测试推送",
                body="这是一条测试消息",
            ),
            data={"test": "true"},
            token=token,
        )
        
        response = messaging.send(message, dry_run=True)  # dry_run=True 不实际发送
        print(f"✅ Token 有效！Response: {response}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Token 无效: {error_msg}")
        
        # 分析错误原因
        if "not a valid FCM registration token" in error_msg:
            print("   原因: Token 格式不正确或已过期")
        elif "Requested entity was not found" in error_msg:
            print("   原因: Token 已注销或不存在")
        elif "SenderId mismatch" in error_msg:
            print("   原因: Token 属于不同的 Firebase 项目！")
            print("   💡 解决方案: 确保 iOS/Android 应用使用相同的 Firebase 项目")
        elif "Expected OAuth 2 access token" in error_msg:
            print("   原因: Firebase 认证失败")
            print("   💡 可能原因:")
            print("      1. Service Account 凭证不正确")
            print("      2. Firebase 项目配置有误")
            print("      3. Token 来自不同的 Firebase 项目")
        
        return False

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 diagnose_push.py <FCM_TOKEN> [platform]")
        print("示例: python3 diagnose_push.py et-_1mI-U0dym7hEgxOJ... iOS")
        sys.exit(1)
    
    token = sys.argv[1]
    platform = sys.argv[2] if len(sys.argv) > 2 else "未知"
    
    initialize_firebase()
    test_token(token, platform)

if __name__ == '__main__':
    main()

