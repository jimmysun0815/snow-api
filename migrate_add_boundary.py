#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：为 resorts 表添加 boundary 字段
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def migrate():
    """执行迁移"""
    # 从环境变量获取数据库配置
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5433')
    db_name = os.getenv('DB_NAME', 'snow')
    db_user = os.getenv('DB_USER', 'app')
    db_pass = os.getenv('DB_PASS', 'app')
    
    # 构建数据库连接字符串
    db_url = f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'
    
    print("=" * 70)
    print("数据库迁移：为 resorts 表添加 boundary 字段")
    print("=" * 70)
    print()
    
    try:
        # 创建引擎
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # 开始事务
            trans = conn.begin()
            
            try:
                print("1. 检查字段是否已存在...")
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'resorts' AND column_name = 'boundary';
                """))
                
                if result.fetchone():
                    print("   ⚠️  boundary 字段已存在，跳过迁移")
                    trans.rollback()
                    return
                
                print("   ✓ boundary 字段不存在，开始添加")
                print()
                
                print("2. 添加 boundary 字段（JSONB 类型）...")
                conn.execute(text("""
                    ALTER TABLE resorts 
                    ADD COLUMN boundary JSONB;
                """))
                print("   ✓ boundary 字段添加成功")
                print()
                
                print("3. 添加注释...")
                conn.execute(text("""
                    COMMENT ON COLUMN resorts.boundary IS '雪场边界多边形坐标 [[lon, lat], ...]';
                """))
                print("   ✓ 注释添加成功")
                print()
                
                # 提交事务
                trans.commit()
                
                print("=" * 70)
                print("✅ 迁移完成！")
                print("=" * 70)
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ 迁移失败: {e}")
        print("=" * 70)
        return False
    
    return True


if __name__ == '__main__':
    migrate()

