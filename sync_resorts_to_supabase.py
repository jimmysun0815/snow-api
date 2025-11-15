#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步雪场数据从 AWS RDS 到 Supabase
用于管理后台访问雪场信息

运行方式：
    python sync_resorts_to_supabase.py

环境变量：
    DATABASE_URL: AWS RDS PostgreSQL 连接字符串
    SUPABASE_URL: Supabase 项目 URL
    SUPABASE_SERVICE_KEY: Supabase Service Key
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入模型
from models import Resort

def get_resorts_from_rds():
    """从 AWS RDS 读取所有雪场数据"""
    print("=" * 80)
    print("📡 从 AWS RDS 读取雪场数据...")
    print("=" * 80)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("❌ 未设置 DATABASE_URL 环境变量")
    
    print(f"🔗 数据库连接: {database_url[:20]}...（已隐藏敏感信息）")
    
    # 连接 RDS
    try:
        engine = create_engine(database_url, echo=False)
    except Exception as e:
        print(f"❌ 创建数据库引擎失败: {e}")
        print(f"📋 DATABASE_URL 格式应该是: postgresql://user:password@host:port/database")
        raise
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 查询所有雪场
        resorts = session.query(Resort).all()
        print(f"✅ 从 RDS 读取到 {len(resorts)} 个雪场")
        
        # 转换为字典列表
        resort_data = []
        for r in resorts:
            resort_data.append({
                'id': r.id,
                'name': r.name,
                'slug': r.slug,
                'location': r.location,
                'lat': r.lat,
                'lon': r.lon,
                'elevation_min': r.elevation_min,
                'elevation_max': r.elevation_max,
                'address': r.address,
                'city': r.city,
                'zip_code': r.zip_code,
                'phone': r.phone,
                'website': r.website,
                'data_source': r.data_source,
                'source_url': r.source_url,
                'enabled': r.enabled,
                'synced_at': datetime.now().isoformat(),
                'updated_at': r.updated_at.isoformat() if r.updated_at else None,
            })
        
        return resort_data
    
    except Exception as e:
        print(f"❌ 读取 RDS 数据失败: {e}")
        raise
    finally:
        session.close()

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
    print("   AWS RDS → Supabase")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # 步骤 1: 从 RDS 读取
        resort_data = get_resorts_from_rds()
        
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

