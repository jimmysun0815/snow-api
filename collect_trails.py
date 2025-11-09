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
from datetime import datetime
from collectors import OSMTrailsCollector
from db_manager import DatabaseManager
from trails_report_html import generate_trails_html_report


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
    skip_count = 0
    total_trails = 0
    
    # 报告数据
    report_resorts = []
    start_time = time.time()
    
    print("=" * 80)
    print()
    
    for i, resort_config in enumerate(resorts, 1):
        resort_name = resort_config.get('name')
        resort_id = resort_config.get('id')
        resort_location = resort_config.get('location', 'N/A')
        
        print(f"[{i}/{len(resorts)}] 📍 {resort_name}")
        
        resort_start_time = time.time()
        resort_report = {
            'resort_id': resort_id,
            'name': resort_name,
            'location': resort_location,
            'status': 'failed',
            'trails_count': 0,
            'boundary_points': 0,
            'error': '',
            'duration': 0,
            'difficulty_stats': {}
        }
        
        try:
            # 先检查数据库是否已有雪道数据
            existing_trails = db_manager.get_resort_trails(resort_id=resort_id)
            
            if existing_trails and len(existing_trails) > 0:
                print(f"   ⏭️  已有 {len(existing_trails)} 条雪道数据，跳过采集")
                skip_count += 1
                total_trails += len(existing_trails)
                
                # 统计难度分布
                difficulty_stats = {'easy': 0, 'intermediate': 0, 'advanced': 0, 'expert': 0}
                for trail in existing_trails:
                    diff = trail.get('difficulty', 'unknown')
                    if diff in difficulty_stats:
                        difficulty_stats[diff] += 1
                
                resort_report['status'] = 'skipped'
                resort_report['trails_count'] = len(existing_trails)
                resort_report['difficulty_stats'] = difficulty_stats
                resort_report['duration'] = time.time() - resort_start_time
                report_resorts.append(resort_report)
                
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
                trail_count = trails_data.get('total_trails', 0)
                boundary_points = len(trails_data.get('boundary', []))
                
                if trail_count > 0:
                    # 保存到数据库
                    success = db_manager.save_trails_data(resort_config, trails_data)
                    
                    if success:
                        print(f"   [OK] 成功 - {trail_count} 条雪道")
                        success_count += 1
                        total_trails += trail_count
                        
                        # 统计难度分布
                        difficulty_stats = {'easy': 0, 'intermediate': 0, 'advanced': 0, 'expert': 0}
                        for trail in trails_data.get('trails', []):
                            diff = trail.get('difficulty', 'unknown')
                            if diff in difficulty_stats:
                                difficulty_stats[diff] += 1
                        
                        resort_report['status'] = 'success'
                        resort_report['trails_count'] = trail_count
                        resort_report['boundary_points'] = boundary_points
                        resort_report['difficulty_stats'] = difficulty_stats
                    else:
                        print(f"   [WARNING]  采集成功但保存失败 - {trail_count} 条雪道")
                        fail_count += 1
                        resort_report['error'] = '保存到数据库失败'
                else:
                    print(f"   [WARNING]  未找到雪道数据")
                    fail_count += 1
                    resort_report['error'] = '未找到雪道数据'
            else:
                print(f"   [ERROR] 采集失败")
                fail_count += 1
                resort_report['error'] = '数据采集失败'
                
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"   [ERROR] 错误: {error_msg}")
            fail_count += 1
            resort_report['error'] = error_msg
        
        resort_report['duration'] = time.time() - resort_start_time
        report_resorts.append(resort_report)
        
        print()
        
        # 每个雪场之间等待5秒，避免API限流
        if i < len(resorts):
            print("⏳ 等待 5 秒...")
            time.sleep(5)
            print()
    
    # 总结
    total_time = time.time() - start_time
    print("=" * 80)
    print(f"[OK] 采集完成!")
    print(f"   成功: {success_count} 个雪场")
    print(f"   跳过: {skip_count} 个雪场")
    print(f"   失败: {fail_count} 个雪场")
    print(f"   总雪道数: {total_trails} 条")
    print(f"   总耗时: {total_time:.1f} 秒")
    print("=" * 80)
    print()
    
    # 生成报告
    print("=" * 80)
    print("📊 生成雪道采集报告...")
    print("=" * 80)
    
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total': len(resorts),
            'success': success_count,
            'failed': fail_count,
            'skipped': skip_count,
            'total_trails': total_trails,
            'total_duration': total_time
        },
        'resorts': report_resorts
    }
    
    # 保存 JSON 报告
    json_report_path = 'data/trails_report.json'
    Path('data').mkdir(exist_ok=True)
    with open(json_report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"[OK] JSON 报告已保存: {json_report_path}")
    
    # 生成 HTML 报告
    html_report_path = 'data/trails_report.html'
    generate_trails_html_report(report_data, html_report_path)
    
    print()
    print("=" * 80)
    print(f"✨ 报告已生成:")
    print(f"   📄 JSON: {json_report_path}")
    print(f"   🌐 HTML: {html_report_path}")
    print("=" * 80)
    print()
    
    # 关闭数据库连接
    db_manager.close()


if __name__ == '__main__':
    main()

