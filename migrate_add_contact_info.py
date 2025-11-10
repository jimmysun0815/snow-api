#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在生产环境（Lambda/RDS）执行数据库迁移
添加联系信息字段
"""

import os
import psycopg2

def lambda_handler(event, context):
    """Lambda handler for database migration"""
    
    # 从环境变量获取数据库配置
    db_config = {
        'host': os.environ.get('POSTGRES_HOST'),
        'port': os.environ.get('POSTGRES_PORT', '5432'),
        'user': os.environ.get('POSTGRES_USER'),
        'password': os.environ.get('POSTGRES_PASSWORD'),
        'database': os.environ.get('POSTGRES_DB')
    }
    
    print(f"🔄 开始数据库迁移...")
    print(f"   数据库: {db_config['database']}")
    print(f"   主机: {db_config['host']}")
    
    try:
        # 连接数据库
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        print("✅ 数据库连接成功")
        
        # 迁移 SQL
        migration_sql = """
        -- 添加联系信息字段（如果不存在）
        DO $$
        BEGIN
            -- 检查并添加 address 字段
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='resorts' AND column_name='address'
            ) THEN
                ALTER TABLE resorts ADD COLUMN address VARCHAR(500);
                COMMENT ON COLUMN resorts.address IS '雪场街道地址';
                RAISE NOTICE 'Added column: address';
            ELSE
                RAISE NOTICE 'Column address already exists, skipping';
            END IF;
            
            -- 检查并添加 city 字段
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='resorts' AND column_name='city'
            ) THEN
                ALTER TABLE resorts ADD COLUMN city VARCHAR(200);
                COMMENT ON COLUMN resorts.city IS '雪场所在城市';
                RAISE NOTICE 'Added column: city';
            ELSE
                RAISE NOTICE 'Column city already exists, skipping';
            END IF;
            
            -- 检查并添加 zip_code 字段
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='resorts' AND column_name='zip_code'
            ) THEN
                ALTER TABLE resorts ADD COLUMN zip_code VARCHAR(50);
                COMMENT ON COLUMN resorts.zip_code IS '邮政编码';
                RAISE NOTICE 'Added column: zip_code';
            ELSE
                RAISE NOTICE 'Column zip_code already exists, skipping';
            END IF;
            
            -- 检查并添加 phone 字段
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='resorts' AND column_name='phone'
            ) THEN
                ALTER TABLE resorts ADD COLUMN phone VARCHAR(100);
                COMMENT ON COLUMN resorts.phone IS '联系电话';
                RAISE NOTICE 'Added column: phone';
            ELSE
                RAISE NOTICE 'Column phone already exists, skipping';
            END IF;
            
            -- 检查并添加 website 字段
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='resorts' AND column_name='website'
            ) THEN
                ALTER TABLE resorts ADD COLUMN website TEXT;
                COMMENT ON COLUMN resorts.website IS '官方网站';
                RAISE NOTICE 'Added column: website';
            ELSE
                RAISE NOTICE 'Column website already exists, skipping';
            END IF;
        END $$;
        """
        
        # 执行迁移
        cursor.execute(migration_sql)
        conn.commit()
        
        print("✅ 迁移执行成功")
        
        # 验证字段是否存在
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name='resorts' 
            AND column_name IN ('address', 'city', 'zip_code', 'phone', 'website')
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        print(f"\n📊 验证新字段:")
        for col_name, col_type in columns:
            print(f"   ✓ {col_name}: {col_type}")
        
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': {
                'message': '数据库迁移成功',
                'fields_added': [col[0] for col in columns]
            }
        }
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': {
                'message': f'数据库迁移失败: {str(e)}'
            }
        }


if __name__ == '__main__':
    # 本地测试
    import sys
    sys.path.insert(0, 'venv/lib/python3.11/site-packages')
    
    from config import Config
    import os
    
    os.environ['POSTGRES_HOST'] = Config.POSTGRES_HOST
    os.environ['POSTGRES_PORT'] = str(Config.POSTGRES_PORT)
    os.environ['POSTGRES_USER'] = Config.POSTGRES_USER
    os.environ['POSTGRES_PASSWORD'] = Config.POSTGRES_PASSWORD
    os.environ['POSTGRES_DB'] = Config.POSTGRES_DB
    
    result = lambda_handler({}, {})
    print(f"\n结果: {result}")

