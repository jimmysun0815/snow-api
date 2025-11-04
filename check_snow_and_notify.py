#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snow Alert Checker
Checks for upcoming snow and sends push notifications
"""

import os
import json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from push_service import send_snow_alert_notification, initialize_firebase


def check_snow_alerts():
    """Check for snow alerts and send notifications"""
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
    )
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all active resort subscriptions
            cur.execute("""
                SELECT 
                    rs.resort_id,
                    rs.user_id,
                    r.name as resort_name
                FROM resort_subscriptions rs
                JOIN resorts r ON r.id = rs.resort_id
                WHERE rs.is_active = TRUE
            """)
            
            subscriptions = cur.fetchall()
            print(f"Found {len(subscriptions)} active subscriptions")
            
            # Group by resort
            resort_subscribers = {}
            for sub in subscriptions:
                resort_id = sub['resort_id']
                if resort_id not in resort_subscribers:
                    resort_subscribers[resort_id] = {
                        'name': sub['resort_name'],
                        'users': []
                    }
                resort_subscribers[resort_id]['users'].append(sub['user_id'])
            
            # Check each resort
            today = datetime.now().date()
            check_date = today + timedelta(days=3)  # Check 3 days ahead
            
            for resort_id, info in resort_subscribers.items():
                try:
                    # Get weather data for the resort
                    cur.execute("""
                        SELECT weather_data
                        FROM resorts
                        WHERE id = %s
                    """, (resort_id,))
                    
                    result = cur.fetchone()
                    if not result or not result['weather_data']:
                        continue
                    
                    weather = result['weather_data']
                    forecast = weather.get('forecast7d', [])
                    
                    # Check for snow on the target date
                    for day in forecast:
                        forecast_date = datetime.fromisoformat(day['date']).date()
                        if forecast_date == check_date:
                            snowfall = day.get('snowfall', 0)
                            
                            # If significant snow (>= 3cm)
                            if snowfall >= 3:
                                # Check if already notified today
                                today_str = today.isoformat()
                                cur.execute("""
                                    SELECT COUNT(*) as count
                                    FROM snow_notification_logs
                                    WHERE resort_id = %s
                                    AND notification_date = %s
                                    AND forecast_date = %s
                                """, (resort_id, today_str, check_date.isoformat()))
                                
                                already_notified = cur.fetchone()['count'] > 0
                                
                                if not already_notified:
                                    # Send notification
                                    print(f"Sending snow alert for {info['name']}: {snowfall}cm on {check_date}")
                                    
                                    result = send_snow_alert_notification(
                                        user_ids=info['users'],
                                        resort_name=info['name'],
                                        snow_date=check_date.strftime('%m月%d日'),
                                        snow_amount=snowfall
                                    )
                                    
                                    # Log notifications
                                    for user_id in info['users']:
                                        cur.execute("""
                                            INSERT INTO snow_notification_logs (
                                                user_id,
                                                resort_id,
                                                notification_date,
                                                forecast_date,
                                                snow_amount,
                                                weather_code,
                                                notification_title,
                                                notification_body
                                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                        """, (
                                            user_id,
                                            resort_id,
                                            today_str,
                                            check_date.isoformat(),
                                            snowfall,
                                            day.get('weather_code'),
                                            f"{info['name']} 降雪预报 ❄️",
                                            f"{check_date.strftime('%m月%d日')} 预计降雪 {snowfall}cm"
                                        ))
                                    
                                    conn.commit()
                                    print(f"Notified {len(info['users'])} users")
                            
                            break
                
                except Exception as e:
                    print(f"Error checking resort {resort_id}: {e}")
                    continue
    
    finally:
        conn.close()


def lambda_handler(event, context):
    """Lambda handler for snow alert checking"""
    try:
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

