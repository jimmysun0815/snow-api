#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪场联系信息采集脚本
使用 Google Places API 获取雪场的地址、电话、网站等静态信息
"""

import argparse
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collectors.google_places import GooglePlacesCollector
from db_manager import DatabaseManager

# 线程锁用于打印
print_lock = threading.Lock()


def collect_single_resort(resort_config, db_manager):
    """
    采集单个雪场的联系信息
    
    Args:
        resort_config: 雪场配置
        db_manager: 数据库管理器
        
    Returns:
        (resort_report, success_flag)
    """
    resort_name = resort_config.get('name')
    resort_id = resort_config.get('id')
    resort_location = resort_config.get('location', 'N/A')
    
    resort_start_time = time.time()
    resort_report = {
        'resort_id': resort_id,
        'name': resort_name,
        'location': resort_location,
        'status': 'failed',
        'error': '',
        'duration': 0,
        'has_address': False,
        'has_phone': False,
        'has_website': False
    }
    
    try:
        # 采集联系信息（Google Places API）
        with print_lock:
            print(f"   📞 [{resort_name}] 采集联系信息...")
        
        places_collector = GooglePlacesCollector(resort_config)
        contact_info = places_collector.collect()
        
        if contact_info:
            # 保存联系信息到数据库
            success = db_manager.save_contact_info(resort_id, contact_info)
            
            if success:
                with print_lock:
                    print(f"   ✅ [{resort_name}] 联系信息已保存")
                
                resort_report['status'] = 'success'
                resort_report['has_address'] = bool(contact_info.get('street_address') or contact_info.get('formatted_address'))
                resort_report['has_phone'] = bool(contact_info.get('phone'))
                resort_report['has_website'] = bool(contact_info.get('website'))
                resort_report['duration'] = time.time() - resort_start_time
                
                return resort_report, 'success'
            else:
                with print_lock:
                    print(f"   ⚠️  [{resort_name}] 保存失败")
                resort_report['error'] = '保存到数据库失败'
                resort_report['duration'] = time.time() - resort_start_time
                return resort_report, 'failed'
        else:
            with print_lock:
                print(f"   ⚠️  [{resort_name}] 未找到联系信息")
            resort_report['error'] = '未找到联系信息'
            resort_report['duration'] = time.time() - resort_start_time
            return resort_report, 'failed'
            
    except Exception as e:
        error_msg = str(e)[:200]
        with print_lock:
            print(f"   ❌ [{resort_name}] 错误: {error_msg}")
        resort_report['error'] = error_msg
        resort_report['duration'] = time.time() - resort_start_time
        return resort_report, 'failed'


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='雪场联系信息采集工具')
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
    print("📇 雪场联系信息采集系统 (Google Places API)")
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
    
    print(f"准备采集 {len(resorts)} 个雪场的联系信息")
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
    
    # 报告数据
    report_resorts = []
    start_time = time.time()
    
    print("=" * 80)
    print(f"🚀 开始并发采集 ({10} 个线程)")
    print("=" * 80)
    print()
    
    # 使用线程池并发采集
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有任务
        future_to_resort = {
            executor.submit(collect_single_resort, resort_config, db_manager): resort_config
            for resort_config in resorts
        }
        
        completed = 0
        for future in as_completed(future_to_resort):
            completed += 1
            resort_config = future_to_resort[future]
            
            try:
                resort_report, status = future.result()
                report_resorts.append(resort_report)
                
                if status == 'success':
                    success_count += 1
                else:
                    fail_count += 1
                
                with print_lock:
                    print(f"   [{completed}/{len(resorts)}] 已完成")
                
            except Exception as e:
                with print_lock:
                    print(f"   ❌ [{resort_config.get('name')}] 线程异常: {str(e)[:100]}")
                fail_count += 1
    
    # 总结
    total_time = time.time() - start_time
    print("=" * 80)
    print(f"[OK] 采集完成!")
    print(f"   成功: {success_count} 个雪场")
    print(f"   失败: {fail_count} 个雪场")
    print(f"   总耗时: {total_time:.1f} 秒")
    print("=" * 80)
    print()
    
    # 生成报告
    print("=" * 80)
    print("📊 生成联系信息采集报告...")
    print("=" * 80)
    
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total': len(resorts),
            'success': success_count,
            'failed': fail_count,
            'total_duration': total_time
        },
        'resorts': report_resorts
    }
    
    # 保存 JSON 报告
    json_report_path = 'data/contact_info_report.json'
    Path('data').mkdir(exist_ok=True)
    with open(json_report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"[OK] 报告已保存: {json_report_path}")
    
    print()
    print("=" * 80)
    print(f"✨ 联系信息采集完成")
    print("=" * 80)
    print()
    
    # 关闭数据库连接
    db_manager.close()


if __name__ == '__main__':
    main()
