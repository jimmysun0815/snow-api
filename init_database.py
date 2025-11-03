#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
创建数据库表并测试连接
"""

from config import Config
from models import init_db, Base
from db_manager import DatabaseManager

def main():
    print("\n" + "=" * 80)
    print("[DB]  数据库初始化")
    print("=" * 80)
    print()
    
    # 显示配置
    Config.display()
    print()
    
    # 1. 创建表
    print("[INFO] 创建数据库表...")
    try:
        engine = init_db(Config.DATABASE_URL)
        print("[OK] 数据库表创建成功!")
        print()
        print("创建的表:")
        for table in Base.metadata.tables:
            print(f"  • {table}")
        print()
    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        return
    
    # 2. 测试连接
    print("=" * 80)
    print("[CHECK] 测试数据库连接...")
    print()
    
    try:
        db_manager = DatabaseManager()
        print("[OK] PostgreSQL 连接成功")
        print("[OK] Redis 连接成功")
        print()
        
        # 测试查询
        resorts = db_manager.get_all_resorts_data()
        print(f"[DATA] 当前数据库中有 {len(resorts)} 个雪场数据")
        print()
        
        db_manager.close()
        
    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        print()
        print("💡 请检查:")
        print("  1. PostgreSQL 是否在运行？")
        print("  2. Redis 是否在运行？")
        print("  3. .env 文件中的配置是否正确？")
        print()
        print("启动数据库:")
        print("  docker-compose up -d")
        print()
        return
    
    print("=" * 80)
    print("[OK] 初始化完成！")
    print("=" * 80)
    print()
    print("下一步:")
    print("  1. 运行数据采集: python collect_data.py")
    print("  2. 启动 API 服务: python api.py")
    print("  3. 访问: http://localhost:8000/api/resorts")
    print()
    print("=" * 80)


if __name__ == '__main__':
    main()


