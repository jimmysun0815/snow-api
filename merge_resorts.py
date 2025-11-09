#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并额外雪场到resorts_config.json
"""

import json
from pathlib import Path


def main():
    print("\n" + "="*80)
    print("🏔️  雪场配置合并工具")
    print("="*80)
    print()
    
    # 读取现有配置
    config_file = Path('resorts_config.json')
    if not config_file.exists():
        print("[ERROR] 找不到 resorts_config.json")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    existing_resorts = config.get('resorts', [])
    print(f"现有雪场数: {len(existing_resorts)}")
    
    # 读取额外雪场
    additional_file = Path('additional_resorts.json')
    if not additional_file.exists():
        print("[ERROR] 找不到 additional_resorts.json")
        return
    
    with open(additional_file, 'r', encoding='utf-8') as f:
        additional_data = json.load(f)
    
    additional_resorts = additional_data.get('additional_resorts', [])
    print(f"额外雪场数: {len(additional_resorts)}")
    print()
    
    # 检查ID冲突
    existing_ids = {r['id'] for r in existing_resorts}
    additional_ids = {r['id'] for r in additional_resorts}
    conflicts = existing_ids & additional_ids
    
    if conflicts:
        print(f"[WARNING] 发现 {len(conflicts)} 个ID冲突:")
        for conflict_id in sorted(conflicts):
            existing = next(r for r in existing_resorts if r['id'] == conflict_id)
            additional = next(r for r in additional_resorts if r['id'] == conflict_id)
            print(f"  ID {conflict_id}: {existing['name']} vs {additional['name']}")
        print()
        print("请解决ID冲突后再运行此脚本")
        return
    
    # 合并雪场
    print("合并雪场...")
    all_resorts = existing_resorts + additional_resorts
    
    # 按ID排序
    all_resorts.sort(key=lambda x: x['id'])
    
    config['resorts'] = all_resorts
    
    # 备份原文件
    backup_file = config_file.with_suffix('.json.backup')
    print(f"备份原配置到: {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # 保存新配置
    print(f"保存新配置到: {config_file}")
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print()
    print("="*80)
    print(f"✅ 合并完成!")
    print(f"   总雪场数: {len(all_resorts)}")
    print(f"   原有: {len(existing_resorts)}")
    print(f"   新增: {len(additional_resorts)}")
    print("="*80)
    print()
    
    # 统计分布
    print("地区分布:")
    from collections import Counter
    locations = [r.get('location', 'N/A') for r in all_resorts]
    location_counts = Counter(locations)
    
    for loc, count in sorted(location_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  {loc}: {count}")
    
    print()
    print(f"按州/省份统计，前20名地区已显示")


if __name__ == '__main__':
    main()

