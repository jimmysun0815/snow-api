#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 mtnpowder 数据源的雪场添加 OnTheSnow URL
"""

import json
import re

def slug_to_onthesnow_url(slug, location):
    """
    根据 slug 和 location 生成 OnTheSnow URL
    """
    # 提取州/省份
    location_lower = location.lower()
    
    # 美国州缩写映射
    us_states = {
        'california': 'california',
        'colorado': 'colorado',
        'utah': 'utah',
        'vermont': 'vermont',
        'wyoming': 'wyoming',
        'montana': 'montana',
        'idaho': 'idaho',
        'washington': 'washington',
        'oregon': 'oregon',
        'new mexico': 'new-mexico',
        'nevada': 'nevada',
        'arizona': 'arizona',
        'new york': 'new-york',
        'new hampshire': 'new-hampshire',
        'maine': 'maine',
        'pennsylvania': 'pennsylvania',
        'alaska': 'alaska',
        'michigan': 'michigan',
        'wisconsin': 'wisconsin',
        'minnesota': 'minnesota',
    }
    
    # 加拿大省份
    canada_provinces = {
        'british columbia': 'british-columbia',
        'alberta': 'alberta',
        'quebec': 'quebec',
        'ontario': 'ontario',
    }
    
    # 查找州/省份
    region = None
    for state, state_slug in {**us_states, **canada_provinces}.items():
        if state in location_lower:
            region = state_slug
            break
    
    if not region:
        return None
    
    # 生成 URL
    return f"https://www.onthesnow.com/{region}/{slug}/skireport"


def main():
    # 读取配置
    with open('resorts_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    updated_count = 0
    
    for resort in config['resorts']:
        # 只处理 mtnpowder 数据源的雪场
        if resort.get('data_source') == 'mtnpowder':
            slug = resort.get('slug')
            location = resort.get('location', '')
            
            # 生成 OnTheSnow URL
            onthesnow_url = slug_to_onthesnow_url(slug, location)
            
            if onthesnow_url:
                resort['onthesnow_url'] = onthesnow_url
                resort['onthesnow_enabled'] = True
                updated_count += 1
                print(f"✅ {resort['name']}: {onthesnow_url}")
            else:
                print(f"⚠️  {resort['name']}: 无法生成 OnTheSnow URL")
    
    # 保存更新后的配置
    with open('resorts_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 完成！更新了 {updated_count} 个雪场")


if __name__ == '__main__':
    main()

