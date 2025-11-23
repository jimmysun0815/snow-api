#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试雪场软删除功能
"""

import os
from dotenv import load_dotenv
from db_manager import DatabaseManager

load_dotenv()

def test_disable_resort(resort_id: int):
    """测试禁用雪场"""
    print(f"\n{'='*80}")
    print(f"测试禁用雪场 ID: {resort_id}")
    print(f"{'='*80}\n")
    
    try:
        # 初始化数据库管理器
        db_manager = DatabaseManager()
        
        # 调用禁用方法
        result = db_manager.disable_resort(resort_id)
        
        print(f"\n✅ 禁用成功:")
        print(f"   Resort ID: {result['resort_id']}")
        print(f"   Resort Name: {result['resort_name']}")
        print(f"   Resort Slug: {result['resort_slug']}")
        
        # 验证结果
        print(f"\n🔍 验证数据库状态...")
        from models import Resort
        session = db_manager.Session()
        resort = session.query(Resort).filter_by(id=resort_id).first()
        
        if resort:
            print(f"   Enabled 状态: {resort.enabled}")
            if resort.enabled == False:
                print(f"   ✅ 验证成功：雪场已被禁用")
            else:
                print(f"   ❌ 验证失败：雪场仍然启用")
        else:
            print(f"   ❌ 验证失败：找不到雪场")
        
        session.close()
        db_manager.close()
        
    except ValueError as e:
        print(f"\n❌ 雪场不存在: {e}")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python test_disable_resort.py <resort_id>")
        print("示例: python test_disable_resort.py 641")
        sys.exit(1)
    
    resort_id = int(sys.argv[1])
    test_disable_resort(resort_id)

