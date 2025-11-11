#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase Push Notification Service
Sends push notifications via Firebase Cloud Messaging
"""

import os
import json
from typing import List, Dict, Optional
import firebase_admin
from firebase_admin import credentials, messaging
import requests

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK with service account"""
    try:
        # Check if already initialized
        firebase_admin.get_app()
        print("Firebase already initialized")
    except ValueError:
        # Initialize with service account key
        cred_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Use environment variables
            # NOTE: FIREBASE_PRIVATE_KEY must be properly formatted with real newlines
            private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '')
            # Replace literal \n with actual newlines
            private_key = private_key.replace('\\n', '\n')
            
            cred_dict = {
                "type": "service_account",
                "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
                "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
                "private_key": private_key,  # Use the processed private_key
                "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
                "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            }
            cred = credentials.Certificate(cred_dict)
        
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully")


def get_user_tokens(user_id: str) -> List[str]:
    """Get all FCM tokens for a user using Supabase REST API"""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
    }
    
    response = requests.get(
        f'{supabase_url}/rest/v1/device_tokens',
        headers=headers,
        params={'user_id': f'eq.{user_id}', 'select': 'token'}
    )
    response.raise_for_status()
    results = response.json()
    
    return [row['token'] for row in results]


def delete_invalid_token(token: str):
    """
    删除失效的 FCM token
    
    Args:
        token: 失效的 FCM token
    """
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
        
        headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}',
        }
        
        response = requests.delete(
            f'{supabase_url}/rest/v1/device_tokens',
            headers=headers,
            params={'token': f'eq.{token}'}
        )
        response.raise_for_status()
        print(f"🗑️  已删除失效 token: {token[:20]}...")
        
    except Exception as e:
        print(f"❌ 删除失效 token 失败: {e}")


def send_push_notification(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict] = None,
    image_url: Optional[str] = None
) -> Dict:
    """
    Send push notification to multiple devices
    
    Args:
        tokens: List of FCM tokens
        title: Notification title
        body: Notification body
        data: Additional data payload
        image_url: Optional image URL
    
    Returns:
        Dict with success_count and failure_count
    """
    if not tokens:
        return {'success_count': 0, 'failure_count': 0}
    
    initialize_firebase()
    
    # Convert all data values to strings (FCM requirement)
    string_data = {}
    if data:
        for key, value in data.items():
            if value is not None:
                string_data[key] = str(value) if not isinstance(value, str) else value
    
    # Send to each token individually (compatible with older firebase-admin versions)
    success_count = 0
    failure_count = 0
    failed_tokens = []
    
    for token in tokens:
        try:
            # Build message for single token
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url
                ),
                data=string_data,
                token=token,
                # iOS specific
                apns=messaging.APNSConfig(
                    headers={'apns-priority': '10'},
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(
                                title=title,
                                body=body,
                            ),
                            badge=1,
                            sound='default',
                        ),
                    ),
                ),
                # Android specific
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        icon='ic_notification',
                        color='#8B5CF6',
                        sound='default',
                        channel_id='high_importance_channel',
                    ),
                ),
            )
            
            # Send message
            response = messaging.send(message)
            success_count += 1
            print(f"✅ Sent to token {token[:20]}...: {response}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to send to token {token[:20]}...: {error_msg}")
            failure_count += 1
            failed_tokens.append(token)
            
            # Check if token is invalid and should be deleted
            should_delete = False
            
            if 'not a valid FCM registration token' in error_msg:
                print(f"   → Token is invalid or expired")
                should_delete = True
            elif 'Requested entity was not found' in error_msg:
                print(f"   → Token was not found (may have been unregistered)")
                should_delete = True
            elif 'SenderId mismatch' in error_msg:
                print(f"   → Token belongs to different Firebase project")
                should_delete = True
            
            # Delete invalid token from database
            if should_delete:
                delete_invalid_token(token)
    
    print(f"✅ Successfully sent {success_count} messages")
    if failure_count > 0:
        print(f"❌ Failed to send {failure_count} messages")
        print(f"   Failed tokens: {[t[:20] + '...' for t in failed_tokens]}")
    
    return {
        'success_count': success_count,
        'failure_count': failure_count,
    }


# Specific notification types

def send_carpool_application_notification(owner_user_id: str, applicant_name: str, carpool_info: Dict):
    """Send notification when someone applies to a carpool"""
    tokens = get_user_tokens(owner_user_id)
    
    return send_push_notification(
        tokens=tokens,
        title=f"🚗 新的拼车申请",
        body=f"{applicant_name} 申请加入你的拼车",
        data={
            'type': 'carpool_application',
            'carpool_id': str(carpool_info.get('id', '')),
        }
    )


def send_carpool_approved_notification(applicant_user_id: str, carpool_info: Dict):
    """Send notification when carpool application is approved"""
    tokens = get_user_tokens(applicant_user_id)
    
    return send_push_notification(
        tokens=tokens,
        title=f"✅ 拼车申请已通过",
        body=f"你的拼车申请已被接受",
        data={
            'type': 'carpool_approved',
            'carpool_id': str(carpool_info.get('id', '')),
        }
    )


def send_carpool_rejected_notification(applicant_user_id: str, carpool_info: Dict):
    """Send notification when carpool application is rejected"""
    tokens = get_user_tokens(applicant_user_id)
    
    return send_push_notification(
        tokens=tokens,
        title=f"❌ 拼车申请未通过",
        body=f"很抱歉，你的拼车申请未被接受",
        data={
            'type': 'carpool_rejected',
            'carpool_id': str(carpool_info.get('id', '')),
        }
    )


def send_accommodation_application_notification(owner_user_id: str, applicant_name: str, accommodation_info: Dict):
    """Send notification when someone applies to accommodation"""
    tokens = get_user_tokens(owner_user_id)
    
    return send_push_notification(
        tokens=tokens,
        title=f"🏠 新的租房申请",
        body=f"{applicant_name} 申请租你的房间",
        data={
            'type': 'accommodation_application',
            'accommodation_id': str(accommodation_info.get('id', '')),
        }
    )


def send_accommodation_approved_notification(applicant_user_id: str, accommodation_info: Dict):
    """Send notification when accommodation application is approved"""
    tokens = get_user_tokens(applicant_user_id)
    
    return send_push_notification(
        tokens=tokens,
        title=f"✅ 租房申请已通过",
        body=f"你的租房申请已被接受",
        data={
            'type': 'accommodation_approved',
            'accommodation_id': str(accommodation_info.get('id', '')),
        }
    )


def send_snow_alert_notification(user_ids: List[str], resort_name: str, snow_date: str, snow_amount: float):
    """Send snow alert notification to multiple users"""
    all_tokens = []
    for user_id in user_ids:
        tokens = get_user_tokens(user_id)
        all_tokens.extend(tokens)
    
    return send_push_notification(
        tokens=all_tokens,
        title=f"❄️ {resort_name} 降雪预报",
        body=f"{snow_date} 预计降雪 {snow_amount}cm",
        data={
            'type': 'snow_alert',
            'resort_name': resort_name,
            'snow_date': snow_date,
            'snow_amount': str(snow_amount),
        }
    )


if __name__ == '__main__':
    # Test
    print("Push notification service loaded")

