#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪场数据采集主程序
运行此脚本来采集所有已启用雪场的数据
"""

import argparse
from resort_manager import ResortDataManager


def main():
    """主函数"""
    
    parser = argparse.ArgumentParser(description='雪场数据采集工具')
    parser.add_argument(
        '--all',
        action='store_true',
        help='采集所有雪场（包括未启用的）'
    )
    parser.add_argument(
        '--resort-id',
        type=int,
        help='只采集指定 ID 的雪场'
    )
    parser.add_argument(
        '--config',
        default='resorts_config.json',
        help='配置文件路径 (默认: resorts_config.json)'
    )
    
    args = parser.parse_args()
    
    # 初始化管理器
    manager = ResortDataManager(config_file=args.config)
    
    print("\n" + "=" * 70)
    print("❄️  雪场数据采集系统")
    print("=" * 70)
    print()
    
    # 单个雪场采集
    if args.resort_id:
        resort_config = None
        for r in manager.resorts:
            if r.get('id') == args.resort_id:
                resort_config = r
                break
        
        if not resort_config:
            print(f"❌ 错误: 找不到 ID 为 {args.resort_id} 的雪场")
            return
        
        print(f"采集单个雪场: {resort_config.get('name')}")
        print()
        
        data = manager.collect_resort_data(resort_config)
        
        if data:
            manager.save_data([data])
            print("\n✅ 采集成功！")
        else:
            print("\n❌ 采集失败")
        
        return
    
    # 批量采集
    enabled_only = not args.all
    results = manager.collect_all(enabled_only=enabled_only)
    
    if results:
        manager.save_data(results)
        print("✅ 采集完成！")
    else:
        print("❌ 没有采集到任何数据")


if __name__ == '__main__':
    main()


