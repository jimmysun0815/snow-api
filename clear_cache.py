#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清除 Redis 缓存工具
用于在修改配置或 URL 后清除缓存
"""

import redis
from config import Config


def clear_all_cache():
    """清除所有缓存"""
    try:
        redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        
        # 获取所有 resort: 开头的 key
        resort_keys = redis_client.keys('resort:*')
        
        if resort_keys:
            # 删除所有雪场缓存
            deleted = redis_client.delete(*resort_keys)
            print(f"✅ 已清除 {deleted} 个雪场缓存")
        else:
            print("ℹ️  没有找到缓存数据")
        
        # 也清除 resorts:all 缓存
        all_key = 'resorts:all'
        if redis_client.exists(all_key):
            redis_client.delete(all_key)
            print(f"✅ 已清除全部雪场列表缓存")
        
        print("🎉 缓存清除完成！")
        
    except Exception as e:
        print(f"❌ 清除缓存失败: {e}")
        print("\n提示: 如果 Redis 未运行，请先启动 Redis:")
        print("  docker-compose up -d redis")
        return False
    
    return True


def clear_resort_cache(resort_id: int):
    """清除单个雪场的缓存"""
    try:
        redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        
        # 清除 ID 缓存
        id_key = f'resort:id:{resort_id}'
        id_deleted = redis_client.delete(id_key)
        
        # 清除全部雪场列表缓存
        all_key = 'resorts:all'
        all_deleted = redis_client.delete(all_key)
        
        if id_deleted or all_deleted:
            print(f"✅ 已清除雪场 ID {resort_id} 的缓存")
        else:
            print(f"ℹ️  雪场 ID {resort_id} 没有缓存")
        
    except Exception as e:
        print(f"❌ 清除缓存失败: {e}")
        return False
    
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='清除 Redis 缓存')
    parser.add_argument(
        '--resort-id',
        type=int,
        help='只清除指定 ID 的雪场缓存'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🗑️  Redis 缓存清除工具")
    print("=" * 70)
    print()
    
    if args.resort_id:
        clear_resort_cache(args.resort_id)
    else:
        clear_all_cache()
    
    print()

