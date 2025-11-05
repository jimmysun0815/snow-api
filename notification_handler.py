#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notification Handler Lambda
Processes push notification queue and sends via Firebase
"""

import os
import json
import requests
from push_service import (
    send_push_notification,
    get_user_tokens,
    initialize_firebase
)


def process_notification_queue():
    """Process pending notifications in the queue using Supabase REST API"""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    
    # Get pending notifications (limit 100 per run)
    response = requests.get(
        f'{supabase_url}/rest/v1/push_notification_queue',
        headers=headers,
        params={
            'status': 'eq.pending',
            'order': 'created_at.asc',
            'limit': 100
        }
    )
    response.raise_for_status()
    notifications = response.json()
    
    print(f"Found {len(notifications)} pending notifications")
    
    for notif in notifications:
        try:
            # Get user tokens
            tokens = get_user_tokens(notif['user_id'])
            
            if not tokens:
                print(f"No tokens found for user {notif['user_id']}")
                # Mark as failed
                requests.patch(
                    f"{supabase_url}/rest/v1/push_notification_queue",
                    headers=headers,
                    params={'id': f"eq.{notif['id']}"},
                    json={
                        'status': 'failed',
                        'error_message': 'No FCM tokens found',
                        'sent_at': 'now()'
                    }
                )
                continue
            
            # Send notification
            result = send_push_notification(
                tokens=tokens,
                title=notif['title'],
                body=notif['body'],
                data=notif.get('data') or {}
            )
            
            # Update status
            if result['success_count'] > 0:
                requests.patch(
                    f"{supabase_url}/rest/v1/push_notification_queue",
                    headers=headers,
                    params={'id': f"eq.{notif['id']}"},
                    json={
                        'status': 'sent',
                        'sent_at': 'now()'
                    }
                )
                print(f"Sent notification {notif['id']} to {result['success_count']} devices")
            else:
                requests.patch(
                    f"{supabase_url}/rest/v1/push_notification_queue",
                    headers=headers,
                    params={'id': f"eq.{notif['id']}"},
                    json={
                        'status': 'failed',
                        'error_message': 'All tokens failed',
                        'sent_at': 'now()'
                    }
                )
        
        except Exception as e:
            print(f"Error processing notification {notif['id']}: {e}")
            try:
                requests.patch(
                    f"{supabase_url}/rest/v1/push_notification_queue",
                    headers=headers,
                    params={'id': f"eq.{notif['id']}"},
                    json={
                        'status': 'failed',
                        'error_message': str(e),
                        'sent_at': 'now()'
                    }
                )
            except:
                pass
    
    return len(notifications)


def lambda_handler(event, context):
    """Lambda handler for notification processing"""
    try:
        initialize_firebase()
        processed_count = process_notification_queue()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {processed_count} notifications',
                'processed_count': processed_count
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

