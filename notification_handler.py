#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notification Handler Lambda
Processes push notification queue and sends via Firebase
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from push_service import (
    send_push_notification,
    get_user_tokens,
    initialize_firebase
)


def process_notification_queue():
    """Process pending notifications in the queue"""
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
    )
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get pending notifications (limit 100 per run)
            cur.execute("""
                SELECT id, user_id, notification_type, title, body, data
                FROM push_notification_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 100
            """)
            
            notifications = cur.fetchall()
            print(f"Found {len(notifications)} pending notifications")
            
            for notif in notifications:
                try:
                    # Get user tokens
                    tokens = get_user_tokens(notif['user_id'])
                    
                    if not tokens:
                        print(f"No tokens found for user {notif['user_id']}")
                        # Mark as failed
                        cur.execute("""
                            UPDATE push_notification_queue
                            SET status = 'failed',
                                error_message = 'No FCM tokens found',
                                sent_at = NOW()
                            WHERE id = %s
                        """, (notif['id'],))
                        continue
                    
                    # Send notification
                    result = send_push_notification(
                        tokens=tokens,
                        title=notif['title'],
                        body=notif['body'],
                        data=notif['data'] or {}
                    )
                    
                    # Update status
                    if result['success_count'] > 0:
                        cur.execute("""
                            UPDATE push_notification_queue
                            SET status = 'sent',
                                sent_at = NOW()
                            WHERE id = %s
                        """, (notif['id'],))
                        print(f"Sent notification {notif['id']} to {result['success_count']} devices")
                    else:
                        cur.execute("""
                            UPDATE push_notification_queue
                            SET status = 'failed',
                                error_message = 'All tokens failed',
                                sent_at = NOW()
                            WHERE id = %s
                        """, (notif['id'],))
                    
                    conn.commit()
                    
                except Exception as e:
                    print(f"Error processing notification {notif['id']}: {e}")
                    cur.execute("""
                        UPDATE push_notification_queue
                        SET status = 'failed',
                            error_message = %s,
                            sent_at = NOW()
                        WHERE id = %s
                    """, (str(e), notif['id']))
                    conn.commit()
            
            return len(notifications)
    
    finally:
        conn.close()


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

