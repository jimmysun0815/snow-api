#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：添加海拔温度字段
"""

from sqlalchemy import create_engine, text
from config import Config

def migrate():
    """添加 temp_base, temp_mid, temp_summit 字段到 resort_weather 表"""
    
    engine = create_engine(Config.DATABASE_URL, echo=True)
    
    print("=" * 80)
    print("🔧 数据库迁移：添加海拔温度字段")
    print("=" * 80)
    print()
    
    with engine.connect() as conn:
        print("📋 检查字段是否已存在...")
        
        # 检查字段是否已存在
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'resort_weather' 
            AND column_name IN ('temp_base', 'temp_mid', 'temp_summit')
        """))
        
        existing_columns = [row[0] for row in result]
        
        if len(existing_columns) == 3:
            print("✅ 字段已存在，无需迁移")
            return
        
        print(f"📝 现有字段: {existing_columns}")
        print()
        
        # 添加字段
        fields_to_add = []
        if 'temp_base' not in existing_columns:
            fields_to_add.append('temp_base')
        if 'temp_mid' not in existing_columns:
            fields_to_add.append('temp_mid')
        if 'temp_summit' not in existing_columns:
            fields_to_add.append('temp_summit')
        
        if fields_to_add:
            print(f"➕ 添加字段: {', '.join(fields_to_add)}")
            print()
            
            for field in fields_to_add:
                sql = f"""
                ALTER TABLE resort_weather 
                ADD COLUMN {field} DOUBLE PRECISION
                """
                print(f"执行: {sql}")
                conn.execute(text(sql))
                print(f"✅ 字段 {field} 添加成功")
                print()
            
            conn.commit()
            print("=" * 80)
            print("✅ 数据库迁移完成！")
            print("=" * 80)
        else:
            print("✅ 所有字段都已存在")

if __name__ == '__main__':
    migrate()

