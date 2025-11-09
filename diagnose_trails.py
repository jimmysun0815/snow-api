#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪道数据诊断脚本
检查失败雪场的OpenStreetMap数据可用性
"""

import json
import requests
import time
import math
from pathlib import Path


def calculate_bbox(lat, lon, radius_km):
    """计算边界框"""
    lat_offset = radius_km / 111.0
    lon_offset = radius_km / (111.0 * math.cos(math.radians(lat)))
    
    south = lat - lat_offset
    north = lat + lat_offset
    west = lon - lon_offset
    east = lon + lon_offset
    
    return f"({south},{west},{north},{east})"


def check_resort_osm_data(resort_config):
    """检查单个雪场的OSM数据"""
    resort_name = resort_config.get('name')
    resort_id = resort_config.get('id')
    lat = resort_config.get('lat')
    lon = resort_config.get('lon')
    
    print(f"\n{'='*80}")
    print(f"检查雪场: {resort_name} (ID: {resort_id})")
    print(f"位置: {lat}, {lon}")
    print(f"{'='*80}")
    
    # 1. 检查雪道数据
    bbox = calculate_bbox(lat, lon, 5)
    
    query = f"""
    [out:json][timeout:25];
    (
      way["piste:type"]{bbox};
      relation["piste:type"]{bbox};
    );
    out count;
    """
    
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={'data': query},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])
            print(f"✓ 在5公里半径内找到 {len(elements)} 个piste:type元素")
            
            # 获取详细数据查看类型分布
            if len(elements) > 0:
                query2 = f"""
                [out:json][timeout:25];
                (
                  way["piste:type"]{bbox};
                  relation["piste:type"]{bbox};
                );
                out tags;
                """
                
                time.sleep(2)
                response2 = requests.post(
                    "https://overpass-api.de/api/interpreter",
                    data={'data': query2},
                    timeout=30
                )
                
                if response2.status_code == 200:
                    data2 = response2.json()
                    elements2 = data2.get('elements', [])
                    
                    # 统计类型
                    piste_types = {}
                    for elem in elements2:
                        tags = elem.get('tags', {})
                        piste_type = tags.get('piste:type', 'unknown')
                        piste_types[piste_type] = piste_types.get(piste_type, 0) + 1
                    
                    print(f"  雪道类型分布:")
                    for ptype, count in sorted(piste_types.items(), key=lambda x: -x[1]):
                        print(f"    - {ptype}: {count}")
        else:
            print(f"✗ HTTP错误: {response.status_code}")
    except Exception as e:
        print(f"✗ 查询失败: {e}")
    
    # 2. 检查边界数据
    time.sleep(2)
    bbox2 = calculate_bbox(lat, lon, 10)
    
    query3 = f"""
    [out:json][timeout:25];
    (
      way["landuse"="winter_sports"]{bbox2};
      relation["landuse"="winter_sports"]{bbox2};
    );
    out tags;
    """
    
    try:
        response3 = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={'data': query3},
            timeout=30
        )
        
        if response3.status_code == 200:
            data3 = response3.json()
            elements3 = data3.get('elements', [])
            print(f"✓ 在10公里半径内找到 {len(elements3)} 个winter_sports边界")
            
            if elements3:
                for elem in elements3[:3]:  # 只显示前3个
                    tags = elem.get('tags', {})
                    name = tags.get('name', 'N/A')
                    print(f"  - {name} (type: {elem.get('type')})")
        else:
            print(f"✗ 边界查询HTTP错误: {response3.status_code}")
    except Exception as e:
        print(f"✗ 边界查询失败: {e}")
    
    # 3. 建议
    print(f"\n建议:")
    if len(elements) == 0:
        print(f"  ⚠️  OpenStreetMap中此雪场缺少雪道数据")
        print(f"  💡 可以考虑:")
        print(f"     1. 检查坐标是否准确")
        print(f"     2. 增加搜索半径")
        print(f"     3. 在OpenStreetMap上贡献雪道数据")
        print(f"     4. 使用其他数据源")
    elif len(elements) < 5:
        print(f"  ⚠️  雪道数据较少，可能需要扩大搜索范围")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("🔍 雪道数据诊断工具")
    print("="*80)
    
    # 加载配置
    config_file = Path('resorts_config.json')
    if not config_file.exists():
        print("[ERROR] 找不到 resorts_config.json")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 加载失败报告
    report_file = Path('data/trails_report.json')
    if not report_file.exists():
        print("[ERROR] 找不到 data/trails_report.json")
        return
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    # 找出所有失败的雪场
    failed_resorts = [r for r in report['resorts'] if r['status'] == 'failed']
    
    print(f"\n找到 {len(failed_resorts)} 个失败的雪场")
    print("\n选择要检查的雪场:")
    print("  1. 检查所有失败的雪场")
    print("  2. 检查特定ID的雪场")
    print("  3. 只检查 'NoneType' 错误的雪场")
    print("  4. 只检查 '未找到雪道数据' 的雪场")
    
    choice = input("\n请选择 (1-4): ").strip()
    
    resorts_to_check = []
    
    if choice == '1':
        resorts_to_check = failed_resorts
    elif choice == '2':
        resort_id = int(input("请输入雪场ID: ").strip())
        resort = next((r for r in failed_resorts if r['resort_id'] == resort_id), None)
        if resort:
            resorts_to_check = [resort]
        else:
            print(f"[ERROR] 找不到ID为 {resort_id} 的失败雪场")
            return
    elif choice == '3':
        resorts_to_check = [r for r in failed_resorts if 'NoneType' in r.get('error', '')]
    elif choice == '4':
        resorts_to_check = [r for r in failed_resorts if '未找到雪道数据' in r.get('error', '')]
    else:
        print("[ERROR] 无效的选择")
        return
    
    print(f"\n将检查 {len(resorts_to_check)} 个雪场")
    
    # 检查每个雪场
    for i, resort_report in enumerate(resorts_to_check, 1):
        resort_id = resort_report['resort_id']
        
        # 从配置中找到完整信息
        resort_config = next((r for r in config['resorts'] if r['id'] == resort_id), None)
        
        if not resort_config:
            print(f"\n[WARNING] 找不到ID {resort_id} 的配置")
            continue
        
        print(f"\n[{i}/{len(resorts_to_check)}]")
        check_resort_osm_data(resort_config)
        
        if i < len(resorts_to_check):
            print("\n等待5秒...")
            time.sleep(5)
    
    print("\n" + "="*80)
    print("诊断完成!")
    print("="*80)


if __name__ == '__main__':
    main()

