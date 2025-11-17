#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda Handler - 雪场联系信息采集
直接调用 collect_trails.py 的逻辑
"""

import json
import sys
import os
from datetime import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collectors.google_places import GooglePlacesCollector
from db_manager import DatabaseManager

def lambda_handler(event, context):
    """Lambda 处理函数"""
    print(f"收到事件: {json.dumps(event)}")
    start_time = datetime.now()
    
    limit = event.get('limit')
    resort_id = event.get('resort_id')
    
    try:
        # 加载配置
        with open('resorts_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        resorts = config.get('resorts', [])
        
        # 初始化数据库管理器
        db_manager = DatabaseManager()
        
        # 单个雪场采集
        if resort_id:
            resort_config = None
            for r in resorts:
                if r.get('id') == resort_id:
                    resort_config = r
                    break
            
            if not resort_config:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': f'Resort ID {resort_id} not found'})
                }
            
            print(f"采集单个雪场联系信息: {resort_config.get('name')}")
            
            # 使用 collect_trails.py 的逻辑
            collector = GooglePlacesCollector(resort_config)
            contact_info = collector.collect()
            
            if contact_info:
                success = db_manager.save_contact_info(resort_id, contact_info)
                if success:
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'message': 'Contact info collected successfully',
                            'resort': resort_config.get('name')
                        })
                    }
                else:
                    return {
                        'statusCode': 500,
                        'body': json.dumps({'error': 'Database save failed'})
                    }
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Contact info not found'})
                }
        
        # 批量采集 - 复用 collect_trails.py 的并发逻辑
        resorts_to_collect = [r for r in resorts if r.get('enabled', False)]
        if limit:
            resorts_to_collect = resorts_to_collect[:limit]
        
        print(f"开始采集 {len(resorts_to_collect)} 个雪场的联系信息（并发）")
        
        success_count = 0
        fail_count = 0
        failed_resorts = []
        
        print_lock = threading.Lock()
        
        def collect_single_resort(resort_config):
            """采集单个雪场 - 与 collect_trails.py 的逻辑一致"""
            resort_name = resort_config.get('name')
            resort_id = resort_config.get('id')
            
            try:
                collector = GooglePlacesCollector(resort_config)
                contact_info = collector.collect()
                
                if contact_info:
                    success = db_manager.save_contact_info(resort_id, contact_info)
                    if success:
                        with print_lock:
                            print(f"   ✅ {resort_name} - 成功")
                        return (True, None)
                    else:
                        with print_lock:
                            print(f"   ❌ {resort_name} - 数据库保存失败")
                        return (False, 'Database save failed')
                else:
                    with print_lock:
                        print(f"   ⚠️  {resort_name} - 未找到联系信息")
                    return (False, 'Contact info not found')
            except Exception as e:
                error_msg = str(e)[:200]
                with print_lock:
                    print(f"   ❌ {resort_name} - 错误: {error_msg}")
                return (False, error_msg)
        
        # 使用线程池并发采集（与 collect_trails.py 一致）
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_resort = {
                executor.submit(collect_single_resort, resort_config): resort_config
                for resort_config in resorts_to_collect
            }
            
            for future in as_completed(future_to_resort):
                resort_config = future_to_resort[future]
                success, error = future.result()
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    failed_resorts.append({
                        'name': resort_config.get('name'),
                        'id': resort_config.get('id'),
                        'error': error
                    })
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ 采集完成: {success_count}/{len(resorts_to_collect)} 成功")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Collected contact info for {success_count} resorts',
                'total_resorts': len(resorts_to_collect),
                'success_count': success_count,
                'fail_count': fail_count,
                'failed_resorts': failed_resorts,
                'duration_seconds': int(duration)
            })
        }
    
    except Exception as e:
        print(f"❌ 采集失败: {e}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'errorType': type(e).__name__
            })
        }

