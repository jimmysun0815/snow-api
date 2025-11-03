#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Lambda 初始化 AWS RDS 数据库
"""

import os
from models import init_db, Base
from db_manager import DatabaseManager


def lambda_handler(event, context):
    """Lambda handler for database initialization"""
    
    print("=" * 80)
    print("🗄️  开始初始化 AWS RDS 数据库")
    print("=" * 80)
    
    # 显示配置
    print(f"\n数据库配置:")
    print(f"  Host: {os.getenv('POSTGRES_HOST')}")
    print(f"  Port: {os.getenv('POSTGRES_PORT')}")
    print(f"  Database: {os.getenv('POSTGRES_DB')}")
    print(f"  User: {os.getenv('POSTGRES_USER')}")
    print(f"\nRedis 配置:")
    print(f"  Host: {os.getenv('REDIS_HOST')}")
    print(f"  Port: {os.getenv('REDIS_PORT')}")
    print()
    
    # 1. 创建表
    print("📝 创建数据库表...")
    try:
        # 构建数据库 URL
        db_url = (
            f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
            f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}"
            f"/{os.getenv('POSTGRES_DB')}"
        )
        
        engine = init_db(db_url)
        
        created_tables = list(Base.metadata.tables.keys())
        print(f"✅ 成功创建 {len(created_tables)} 个表:")
        for table in created_tables:
            print(f"  • {table}")
        print()
        
    except Exception as e:
        error_msg = f"❌ 创建表失败: {str(e)}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': error_msg
        }
    
    # 2. 测试连接
    print("=" * 80)
    print("🔍 测试数据库连接...")
    print()
    
    try:
        db_manager = DatabaseManager()
        print("✅ PostgreSQL 连接成功")
        print("✅ Redis 连接成功")
        print()
        
        # 测试查询
        resorts = db_manager.get_all_resorts_data()
        resort_count = len(resorts)
        print(f"📊 当前数据库中有 {resort_count} 个雪场数据")
        print()
        
        db_manager.close()
        
    except Exception as e:
        error_msg = f"❌ 连接测试失败: {str(e)}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': error_msg
        }
    
    print("=" * 80)
    print("✅ 数据库初始化完成！")
    print("=" * 80)
    print()
    print("下一步:")
    print("  1. 运行数据采集: 手动触发 resort-data-collector Lambda")
    print("  2. 测试 API: curl https://api.steponsnow.com/api/resorts")
    print()
    
    return {
        'statusCode': 200,
        'body': f'Database initialized successfully! Created {len(created_tables)} tables. Current resorts: {resort_count}'
    }


if __name__ == '__main__':
    # 本地测试
    print("⚠️  本地测试模式 - 请确保已设置环境变量")
    lambda_handler({}, {})

