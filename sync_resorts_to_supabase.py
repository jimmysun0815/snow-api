#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步雪场数据从 RDS 到 Supabase
只同步 enabled=true 的雪场（软删除逻辑）

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

def get_resorts_from_rds():
    """
    通过 API 从 RDS 获取雪场数据
    
    🔥 只获取 enabled=true 的雪场（软删除逻辑）
    """
    print("=" * 80)
    print("📡 通过 API 从 RDS 获取启用的雪场数据...")
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
        
        # 🔥 只保留 enabled=true 的雪场
        resort_data = []
        disabled_count = 0
        
        for r in resorts:
            enabled = r.get('enabled', True)
            
            # 跳过已禁用的雪场
            if not enabled:
                disabled_count += 1
                continue
            
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
                'enabled': True,  # 同步到 Supabase 的都是启用的
                'synced_at': datetime.now().isoformat(),
                'updated_at': r.get('updated_at'),
            })
        
        print(f"✅ 过滤后: {len(resort_data)} 个启用的雪场, {disabled_count} 个已禁用")
        
        return resort_data
    
    except requests.exceptions.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        raise
    except Exception as e:
        print(f"❌ 处理数据失败: {e}")
        raise

def sync_to_supabase(resort_data):
    """
    将雪场数据同步到 Supabase
    
    🔥 软删除逻辑：
    1. 删除 Supabase 中所有雪场
    2. 从 RDS 重新插入 enabled=true 的雪场
    3. RDS 的 enabled 字段是唯一的控制开关
    """
    print("=" * 80)
    print("📤 同步启用的雪场到 Supabase (完全覆盖)...")
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
        
        # 🔥 第1步：删除 Supabase 中所有雪场
        print(f"🗑️  删除 Supabase 中所有现有雪场...")
        try:
            # 获取所有雪场 ID
            existing_response = supabase.table('resorts').select('id').execute()
            existing_ids = [item['id'] for item in existing_response.data]
            
            if existing_ids:
                print(f"   找到 {len(existing_ids)} 个现有雪场，准备删除...")
                # 批量删除
                supabase.table('resorts').delete().in_('id', existing_ids).execute()
                print(f"✅ 已删除所有现有雪场")
            else:
                print(f"ℹ️  Supabase 中没有现有雪场")
        except Exception as e:
            print(f"⚠️  删除现有雪场时出错: {e}")
            # 继续执行，因为可能只是没有数据
        
        # 🔥 第2步：从 resorts_config.json 插入所有雪场
        print(f"\n🔄 开始插入 {len(resort_data)} 条数据...")
        
        # 打印第一条数据的字段，用于调试
        if resort_data:
            print(f"📋 数据字段示例（第一个雪场）：")
            first_resort = resort_data[0]
            for key in ['id', 'name', 'slug', 'location', 'enabled']:
                value = first_resort.get(key)
                print(f"   {key}: {value}")
            print()
        
        # Supabase 的插入有批量限制，我们分批处理
        batch_size = 100
        total_synced = 0
        
        print("📝 插入策略：全新插入所有雪场")
        print()
        
        for i in range(0, len(resort_data), batch_size):
            batch = resort_data[i:i + batch_size]
            
            try:
                # 直接插入
                response = supabase.table('resorts').insert(batch).execute()
                
                total_synced += len(batch)
                print(f"   进度: {total_synced}/{len(resort_data)}")
            except Exception as batch_error:
                print(f"   ⚠️  批次 {i}-{i+len(batch)} 插入失败: {batch_error}")
                # 尝试逐个插入以找出问题
                for item in batch:
                    try:
                        supabase.table('resorts').insert([item]).execute()
                        total_synced += 1
                    except Exception as item_error:
                        print(f"      ❌ 雪场 ID {item['id']} ({item['name']}) 插入失败: {item_error}")
                print(f"   进度: {total_synced}/{len(resort_data)}")
        
        print(f"✅ 同步完成！共插入 {total_synced} 个雪场")
        
        # 验证数据
        count_response = supabase.table('resorts').select('*', count='exact').execute()
        print(f"\n✅ Supabase 中现有 {count_response.count} 个雪场")
        print(f"✅ 配置文件中有 {len(resort_data)} 个雪场")
        
        if count_response.count == len(resort_data):
            print(f"🎉 数据完全同步！")
        else:
            print(f"⚠️  数据不一致: Supabase {count_response.count} vs 配置文件 {len(resort_data)}")
        
        return True
    
    except Exception as e:
        print(f"❌ 同步到 Supabase 失败: {e}")
        import traceback
        traceback.print_exc()
        raise

def main():
    """主函数"""
    # ⛔ 2026-11 已废弃：Supabase 的 public.resorts 现在是唯一真源（RDS 已下线）。
    # 本脚本「先删光 Supabase 全部雪场再重插」，而 resort_conditions / weather /
    # webcams / trails 对 resorts 是 ON DELETE CASCADE —— 跑一次就清空所有雪况数据。
    if os.getenv('I_KNOW_THIS_WIPES_RESORT_DATA') != '1':
        print("⛔ sync_resorts_to_supabase.py 已废弃，见文件内注释。")
        sys.exit(1)
    print("\n")
    print("=" * 80)
    print("🔄 雪场数据同步工具")
    print("   RDS (enabled=true) → Supabase (完全覆盖)")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # 步骤 1: 从 RDS 获取启用的雪场
        resort_data = get_resorts_from_rds()
        
        if not resort_data:
            print("❌ RDS 中没有启用的雪场数据")
            sys.exit(1)
        
        # 步骤 2: 同步到 Supabase (完全覆盖)
        sync_to_supabase(resort_data)
        
        print("=" * 80)
        print("✅ 同步任务完成！")
        print("🔥 只同步了 enabled=true 的雪场")
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

