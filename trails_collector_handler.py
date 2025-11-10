#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda 函数 - 雪道数据采集
直接在 Lambda 中运行 collect_trails.py 的逻辑
"""

import json
import sys
import os

def lambda_handler(event, context):
    """Lambda 处理函数"""
    
    print(f"收到事件: {json.dumps(event)}")
    
    # 从事件中获取参数
    limit = event.get('limit')
    resort_id = event.get('resort_id')
    resort_slug = event.get('resort_slug')
    
    # 构建命令行参数
    args = []
    if limit:
        args.extend(['--limit', str(limit)])
    if resort_id:
        args.extend(['--resort-id', str(resort_id)])
    if resort_slug:
        args.extend(['--resort-slug', resort_slug])
    
    print(f"开始采集雪道数据，参数: {args}")
    
    try:
        # 导入并运行 collect_trails 主函数
        from collect_trails import main as collect_trails_main
        
        # 临时修改 sys.argv
        original_argv = sys.argv
        sys.argv = ['collect_trails.py'] + args
        
        try:
            collect_trails_main()
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Trail data collection completed successfully',
                    'limit': limit,
                    'resort_id': resort_id,
                    'resort_slug': resort_slug
                })
            }
        finally:
            sys.argv = original_argv
            
    except Exception as e:
        print(f"❌ 采集失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Trail data collection failed',
                'error': str(e)
            })
        }

# 用于本地测试
if __name__ == '__main__':
    # 本地测试
    test_event = {
        'limit': 5
    }
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
