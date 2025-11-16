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
                'opening_hours_weekday': r.get('opening_hours_weekday'),
                'opening_hours_data': r.get('opening_hours_data'),
                'is_open_now': r.get('is_open_now'),
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
        # 检查表结构（通过尝试查询这些字段）
        print("🔍 检查 Supabase 表结构...")
        try:
            test_query = supabase.table('resorts').select(
                'id, name, opening_hours_weekday, opening_hours_data, is_open_now'
            ).limit(1).execute()
            print("✅ 表结构包含营业时间字段")
        except Exception as e:
            print(f"⚠️  表结构检查失败: {e}")
            print("💡 请确认 Supabase 的 resorts 表中已添加以下列：")
            print("   - opening_hours_weekday (TEXT)")
            print("   - opening_hours_data (JSONB)")
            print("   - is_open_now (BOOLEAN)")
            print()
        
        # 批量 upsert（如果存在则更新，不存在则插入）
        print(f"🔄 开始 upsert {len(resort_data)} 条数据...")
        
        # 打印第一条数据的字段，用于调试
        if resort_data:
            print(f"📋 数据字段示例（第一个雪场）：")
            first_resort = resort_data[0]
            for key in ['id', 'name', 'opening_hours_weekday', 'is_open_now']:
                value = first_resort.get(key)
                if isinstance(value, str) and len(value) > 50:
                    print(f"   {key}: {value[:50]}...")
                else:
                    print(f"   {key}: {value}")
            print()
        
        # Supabase 的 upsert 有批量限制，我们分批处理
        batch_size = 100
        total_synced = 0
        
        for i in range(0, len(resort_data), batch_size):
            batch = resort_data[i:i + batch_size]
            # onConflict='id' 确保按 id 字段进行 upsert
            # ignoreDuplicates=False 确保更新所有字段（包括新添加的营业时间字段）
            response = supabase.table('resorts').upsert(
                batch,
                on_conflict='id',  # 明确指定按 id 字段冲突检测
                ignore_duplicates=False  # 强制更新所有字段，不忽略重复项
            ).execute()
            total_synced += len(batch)
            print(f"   进度: {total_synced}/{len(resort_data)}")
        
        print(f"✅ 同步完成！共同步 {total_synced} 个雪场")
        
        # 验证数据
        count_response = supabase.table('resorts').select('*', count='exact').execute()
        print(f"✅ Supabase 中现有 {count_response.count} 个雪场")
        
        # 验证营业时间字段是否正确同步（检查第一个有营业时间的雪场）
        print("\n🔍 验证营业时间字段...")
        sample_resort = supabase.table('resorts').select(
            'id, name, opening_hours_weekday, is_open_now'
        ).limit(5).execute()
        
        if sample_resort.data:
            print(f"📋 前5个雪场的营业时间状态：")
            for r in sample_resort.data:
                has_hours = r.get('opening_hours_weekday') is not None
                print(f"   {r.get('name')}: {'✅ 有营业时间' if has_hours else '❌ 无营业时间'} (is_open_now: {r.get('is_open_now')})")
        
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

