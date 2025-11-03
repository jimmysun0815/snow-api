#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪道数据采集脚本
从 OpenStreetMap 获取雪道数据并存入数据库
"""

import argparse
import json
import time
from pathlib import Path
from collectors import OSMTrailsCollector
from db_manager import DatabaseManager


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='雪道数据采集工具')
    parser.add_argument(
        '--resort-id',
        type=int,
        help='只采集指定 ID 的雪场'
    )
    parser.add_argument(
        '--resort-slug',
        type=str,
        help='只采集指定 slug 的雪场'
    )
    parser.add_argument(
        '--config',
        default='resorts_config.json',
        help='配置文件路径 (默认: resorts_config.json)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='限制采集数量'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🗺️  雪道数据采集系统 (OpenStreetMap)")
    print("=" * 80)
    print()
    
    # 加载配置
    config_file = Path(args.config)
    if not config_file.exists():
        print(f"[ERROR] 错误: 找不到配置文件 {args.config}")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    resorts = config.get('resorts', [])
    
    # 筛选雪场
    if args.resort_id:
        resorts = [r for r in resorts if r.get('id') == args.resort_id]
        if not resorts:
            print(f"[ERROR] 错误: 找不到 ID 为 {args.resort_id} 的雪场")
            return
    elif args.resort_slug:
        resorts = [r for r in resorts if r.get('slug') == args.resort_slug]
        if not resorts:
            print(f"[ERROR] 错误: 找不到 slug 为 {args.resort_slug} 的雪场")
            return
    else:
        # 只采集启用的雪场
        resorts = [r for r in resorts if r.get('enabled', False)]
    
    # 限制数量
    if args.limit:
        resorts = resorts[:args.limit]
    
    print(f"准备采集 {len(resorts)} 个雪场的雪道数据")
    print()
    
    # 初始化数据库管理器
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        return
    
    # 采集数据
    success_count = 0
    fail_count = 0
    
    print("=" * 80)
    print()
    
    for i, resort_config in enumerate(resorts, 1):
        resort_name = resort_config.get('name')
        resort_id = resort_config.get('id')
        
        print(f"[{i}/{len(resorts)}] 📍 {resort_name}")
        
        try:
            # 先检查数据库是否已有雪道数据
            existing_trails = db_manager.get_resort_trails(resort_id=resort_id)
            
            if existing_trails and len(existing_trails) > 0:
                print(f"   ⏭️  已有 {len(existing_trails)} 条雪道数据，跳过采集")
                success_count += 1
                print()
                
                # 等待后继续下一个
                if i < len(resorts):
                    print("⏳ 等待 5 秒...")
                    time.sleep(5)
                    print()
                continue
            
            # 采集雪道数据
            collector = OSMTrailsCollector(resort_config)
            trails_data = collector.collect()
            
            if trails_data:
                total_trails = trails_data.get('total_trails', 0)
                
                if total_trails > 0:
                    # 保存到数据库
                    success = db_manager.save_trails_data(resort_config, trails_data)
                    
                    if success:
                        print(f"   [OK] 成功 - {total_trails} 条雪道")
                        success_count += 1
                    else:
                        print(f"   [WARNING]  采集成功但保存失败 - {total_trails} 条雪道")
                        fail_count += 1
                else:
                    print(f"   [WARNING]  未找到雪道数据")
                    fail_count += 1
            else:
                print(f"   [ERROR] 采集失败")
                fail_count += 1
                
        except Exception as e:
            print(f"   [ERROR] 错误: {str(e)[:100]}")
            fail_count += 1
        
        print()
        
        # 每个雪场之间等待5秒，避免API限流
        if i < len(resorts):
            print("⏳ 等待 5 秒...")
            time.sleep(5)
            print()
    
    # 总结
    print("=" * 80)
    print(f"[OK] 采集完成!")
    print(f"   成功: {success_count} 个雪场")
    print(f"   失败: {fail_count} 个雪场")
    print("=" * 80)
    print()
    
    # 关闭数据库连接
    db_manager.close()


if __name__ == '__main__':
    main()

