#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪场数据采集主程序
运行此脚本来采集所有已启用雪场的数据
"""

import argparse
import json
from resort_manager import ResortDataManager
from failure_tracker import CollectionFailureTracker


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
    
    # 初始化失败追踪器
    failure_tracker = CollectionFailureTracker()
    
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
            print(f"[ERROR] 错误: 找不到 ID 为 {args.resort_id} 的雪场")
            return
        
        print(f"采集单个雪场: {resort_config.get('name')}")
        print()
        
        data = manager.collect_resort_data(resort_config)
        
        if data:
            manager.save_data([data])
            print("\n[OK] 采集成功！")
        else:
            print("\n[ERROR] 采集失败")
        
        return
    
    # 批量采集
    enabled_only = not args.all
    results = manager.collect_all(enabled_only=enabled_only, failure_tracker=failure_tracker)
    
    # 统计失败的雪场
    expected_count = len([r for r in manager.resorts if r.get('enabled', True)]) if enabled_only else len(manager.resorts)
    actual_count = len(results)
    failed_count = expected_count - actual_count
    
    print(f"\n采集完成: {actual_count}/{expected_count} 个雪场")
    if failed_count > 0:
        print(f"⚠️ {failed_count} 个雪场采集失败")
        
        # 打印失败摘要
        failure_tracker.print_summary()
        
        # 保存失败记录
        failure_tracker.save()
    
    if results:
        manager.save_data(results)
        print("[OK] 采集完成！")
        
        # 生成监控报告
        print("\n" + "=" * 70)
        print("📊 生成数据监控报告...")
        print("=" * 70)
        try:
            from monitor import DataMonitor
            from monitor_html import generate_html_report
            from monitor_history import MonitorHistory
            
            # 创建监控器
            monitor = DataMonitor()
            
            # 执行监控分析
            reports = monitor.monitor_all('data/latest.json')
            
            if reports:
                # 打印摘要
                monitor.print_summary()
                
                # 保存 JSON 报告
                monitor.save_report('data/monitor_report.json')
                
                # 读取并添加失败信息到报告
                with open('data/monitor_report.json', 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                
                # 添加采集失败信息
                report_data['collection_failures'] = failure_tracker.failures
                report_data['summary']['collection_failed'] = len(failure_tracker.failures)
                report_data['summary']['collection_success'] = actual_count
                report_data['summary']['collection_total'] = expected_count
                
                # 保存更新后的报告
                with open('data/monitor_report.json', 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
                
                # 生成 HTML 报告
                generate_html_report('data/monitor_report.json', 'data/monitor_report.html')
                
                # 添加到历史记录
                try:
                    history = MonitorHistory()
                    history.add_record(report_data)
                    print(f"[OK] 已更新历史记录")
                except Exception as e:
                    print(f"[WARNING] 历史记录更新失败: {e}")
                
                # 显示趋势分析
                try:
                    history = MonitorHistory()
                    trend_report = history.generate_summary_report(days=7)
                    print(trend_report)
                except Exception as e:
                    print(f"[WARNING] 趋势分析失败: {e}")
                
                print(f"[OK] 监控报告生成完成！")
                print(f"     JSON: data/monitor_report.json")
                print(f"     HTML: data/monitor_report.html")
                print()
            else:
                print("[WARNING] 无法生成监控报告")
        except Exception as e:
            print(f"[ERROR] 监控报告生成失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[ERROR] 没有采集到任何数据")


if __name__ == '__main__':
    main()



