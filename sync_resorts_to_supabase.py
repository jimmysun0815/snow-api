#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步雪场数据从 AWS RDS 到 Supabase
通过 API Gateway 获取数据（不直接连接 RDS）

运行方式：
    python sync_resorts_to_supabase.py

环境变量：
    API_BASE_URL: 后端 API 地址（默认：https://api.steponsnow.com）
    SUPABASE_URL: Supabase 项目 URL
    SUPABASE_SERVICE_KEY: Supabase Service Key
"""

import os
import sys
import requests
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_resorts_from_api():
    """通过 API 获取所有雪场数据"""
    print("=" * 80)
    print("📡 通过 API 获取雪场数据...")
    print("=" * 80)
    
    api_base_url = os.getenv('API_BASE_URL', 'https://api.steponsnow.com')
    api_url = f"{api_base_url}/api/resorts/summary"
    
    print(f"🔗 API 地址: {api_url}")
    
    try:
        # 调用 API
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        resorts = data.get('resorts', [])
        
        print(f"✅ 从 API 获取到 {len(resorts)} 个雪场")
        
        # 格式化数据（添加同步时间戳）
        resort_data = []
        for r in resorts:
            resort_data.append({
                'id': r.get('id'),
                'name': r.get('name'),
                'slug': r.get('slug'),
                'location': r.get('location'),
                'lat': r.get('lat'),
                'lon': r.get('lon'),
                'elevation_min': r.get('elevation_min'),
                'elevation_max': r.get('elevation_max'),
                'address': r.get('address'),
                'city': r.get('city'),
                'zip_code': r.get('zip_code'),
                'phone': r.get('phone'),
                'website': r.get('website'),
                'data_source': r.get('data_source'),
                'source_url': r.get('source_url'),
                'enabled': r.get('enabled', True),
                'synced_at': datetime.now().isoformat(),
                'updated_at': r.get('updated_at'),
            })
        
        return resort_data
    
    except requests.exceptions.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        raise
    except Exception as e:
        print(f"❌ 处理数据失败: {e}")
        raise

def sync_to_supabase(resort_data):
    """将雪场数据同步到 Supabase"""
    print("=" * 80)
    print("📤 同步数据到 Supabase...")
    print("=" * 80)
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("❌ 未设置 SUPABASE_URL 或 SUPABASE_SERVICE_KEY")
    
    # 连接 Supabase
    supabase: Client = create_client(supabase_url, supabase_key)
    
    try:
        # 批量 upsert（如果存在则更新，不存在则插入）
        print(f"🔄 开始 upsert {len(resort_data)} 条数据...")
        
        # Supabase 的 upsert 有批量限制，我们分批处理
        batch_size = 100
        total_synced = 0
        
        for i in range(0, len(resort_data), batch_size):
            batch = resort_data[i:i + batch_size]
            response = supabase.table('resorts').upsert(batch).execute()
            total_synced += len(batch)
            print(f"   进度: {total_synced}/{len(resort_data)}")
        
        print(f"✅ 同步完成！共同步 {total_synced} 个雪场")
        
        # 验证数据
        count_response = supabase.table('resorts').select('*', count='exact').execute()
        print(f"✅ Supabase 中现有 {count_response.count} 个雪场")
        
        return True
    
    except Exception as e:
        print(f"❌ 同步到 Supabase 失败: {e}")
        import traceback
        traceback.print_exc()
        raise

def main():
    """主函数"""
    print("\n")
    print("=" * 80)
    print("🔄 雪场数据同步工具")
    print("   API Gateway → Supabase")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # 步骤 1: 从 API 获取
        resort_data = get_resorts_from_api()
        
        # 步骤 2: 同步到 Supabase
        sync_to_supabase(resort_data)
        
        print("=" * 80)
        print("✅ 同步任务完成！")
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print("\n")
        
        return 0
    
    except Exception as e:
        print("=" * 80)
        print(f"❌ 同步任务失败: {e}")
        print("=" * 80)
        print("\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())

