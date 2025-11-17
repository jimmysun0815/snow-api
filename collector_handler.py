#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda Handler - 雪场数据采集
直接调用 collect_data.py 的逻辑
"""

import json
import sys
import os
from datetime import datetime

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resort_manager import ResortDataManager
from failure_tracker import CollectionFailureTracker
from s3_uploader import S3ReportUploader
from monitor import DataMonitor

def lambda_handler(event, context):
    """Lambda 处理函数"""
    print(f"收到事件: {json.dumps(event)}")
    start_time = datetime.now()
    limit = event.get('limit')
    resort_id = event.get('resort_id')
    uploader = S3ReportUploader()
    
    try:
        manager = ResortDataManager(config_file='resorts_config.json')
        failure_tracker = CollectionFailureTracker()
        
        # 单个雪场采集
        if resort_id:
            resort_config = None
            for r in manager.resorts:
                if r.get('id') == resort_id:
                    resort_config = r
                    break
            
            if not resort_config:
                return {'statusCode': 404, 'body': json.dumps({'error': f'Resort ID {resort_id} not found'})}
            
            print(f"采集单个雪场: {resort_config.get('name')}")
            data = manager.collect_resort_data(resort_config)
            
            if data:
                manager.save_data([data])
                end_time = datetime.now()
                monitor_data = run_data_quality_check(manager)
                stats = {
                    'start_time': start_time, 
                    'end_time': end_time,
                    'total_resorts': 1, 
                    'success_count': 1, 
                    'fail_count': 0,
                    'failed_resorts': []
                }
                generate_and_upload_report(uploader, stats, monitor_data)
                return {'statusCode': 200, 'body': json.dumps({'message': 'Data collected successfully', 'resort': resort_config.get('name')})}
            else:
                end_time = datetime.now()
                stats = {
                    'start_time': start_time, 
                    'end_time': end_time,
                    'total_resorts': 1, 
                    'success_count': 0, 
                    'fail_count': 1,
                    'failed_resorts': [{'name': resort_config.get('name'), 'error': 'Collection failed'}]
                }
                generate_and_upload_report(uploader, stats, None)
                return {'statusCode': 500, 'body': json.dumps({'error': 'Collection failed'})}
        
        # 批量采集 - 使用 manager.collect_all() 方法
        resorts_to_collect = [r for r in manager.resorts if r.get('enabled', False)]
        if limit:
            resorts_to_collect = resorts_to_collect[:limit]
        
        print(f"开始采集 {len(resorts_to_collect)} 个雪场（并发）")
        results = manager.collect_all(enabled_only=True, failure_tracker=failure_tracker, max_workers=10)
        
        print(f"✅ 采集完成: {len(results)}/{len(resorts_to_collect)}")
        
        if results:
            manager.save_data(results)
        
        # 执行数据质量监控
        print("📊 开始数据质量监控...")
        monitor_data = run_data_quality_check(manager)
        
        end_time = datetime.now()
        stats = {
            'start_time': start_time, 'end_time': end_time,
            'total_resorts': len(resorts_to_collect),
            'success_count': len(results), 
            'fail_count': len(failure_tracker.failures),
            'failed_resorts': failure_tracker.failures
        }
        report_url = generate_and_upload_report(uploader, stats, monitor_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Collected {len(results)} resorts successfully',
                'total_resorts': len(resorts_to_collect),
                'success_count': len(results), 
                'fail_count': len(failure_tracker.failures),
                'report_url': report_url
            })
        }
    except Exception as e:
        print(f"❌ 采集失败: {e}")
        import traceback
        traceback.print_exc()
        end_time = datetime.now()
        stats = {
            'start_time': start_time, 'end_time': end_time,
            'total_resorts': 0, 'success_count': 0, 'fail_count': 1,
            'failed_resorts': [{'name': 'System Error', 'error': str(e)}]
        }
        try:
            generate_and_upload_report(uploader, stats, None)
        except:
            pass
        return {'statusCode': 500, 'body': json.dumps({'error': str(e), 'errorType': type(e).__name__})}

def run_data_quality_check(manager):
    """执行数据质量监控"""
    try:
        # 从数据库获取所有雪场的最新数据
        print("📊 从数据库读取最新雪场数据...")
        all_resorts_data = manager.db_manager.get_all_resorts_data()
        
        if not all_resorts_data or len(all_resorts_data) == 0:
            print("⚠️ 数据库中没有雪场数据，无法生成监控报告")
            return None
        
        print(f"✅ 从数据库读取到 {len(all_resorts_data)} 个雪场数据")
        
        # 构造符合 monitor.monitor_all() 期望的格式
        latest_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_resorts': len(all_resorts_data)
            },
            'resorts': all_resorts_data
        }
        
        # 保存到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(latest_data, f, ensure_ascii=False, indent=2)
            temp_file = f.name
        
        # 执行监控
        monitor = DataMonitor()
        reports = monitor.monitor_all(temp_file)
        
        # 删除临时文件
        os.unlink(temp_file)
        
        if reports:
            # 将 dataclass 对象转换为字典
            from dataclasses import asdict
            reports_dict = [asdict(r) for r in reports]
            
            # 生成监控报告数据
            monitor_data = {
                'summary': {
                    'total_resorts': len(reports_dict),
                    'status_counts': {
                        'good': sum(1 for r in reports if r.overall_status == 'good'),
                        'success': sum(1 for r in reports if r.overall_status == 'success'),
                        'warning': sum(1 for r in reports if r.overall_status == 'warning'),
                        'error': sum(1 for r in reports if r.overall_status == 'error')
                    }
                },
                'resorts': reports_dict
            }
            
            # 修正状态计数的键名
            monitor_data['summary']['success'] = monitor_data['summary']['status_counts'].get('good', 0) + monitor_data['summary']['status_counts'].get('success', 0)
            monitor_data['summary']['warning'] = monitor_data['summary']['status_counts']['warning']
            monitor_data['summary']['error'] = monitor_data['summary']['status_counts']['error']
            
            print(f"✅ 数据质量监控完成: {len(reports_dict)} 个雪场")
            print(f"   正常: {monitor_data['summary']['success']}, 警告: {monitor_data['summary']['warning']}, 错误: {monitor_data['summary']['error']}")
            return monitor_data
        else:
            print("⚠️ 监控未返回数据")
            return None
    except Exception as e:
        print(f"⚠️ 数据质量监控失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_and_upload_report(uploader, stats, monitor_data):
    """生成并上传报告"""
    try:
        from monitor_html import generate_html_report as generate_monitor_html
        import tempfile
        
        # 计算运行时长
        duration_seconds = (stats['end_time'] - stats['start_time']).total_seconds()
        
        # 构建完整的监控报告数据
        report_data = {
            'timestamp': stats['start_time'].isoformat(),
            'duration_seconds': duration_seconds,
            'summary': {
                'total_resorts': 0,
                'success': 0,
                'warning': 0,
                'error': 0,
                'collection_total': stats.get('total_resorts', 0),
                'collection_success': stats.get('success_count', 0),
                'collection_failed': stats.get('fail_count', 0)
            },
            'resorts': [],
            'collection_failures': stats.get('failed_resorts', [])
        }
        
        # 填充 summary 和 resorts（如果有监控数据）
        if monitor_data:
            if 'summary' in monitor_data:
                report_data['summary']['total_resorts'] = monitor_data['summary'].get('total_resorts', 0)
                report_data['summary']['success'] = monitor_data['summary'].get('success', 0)
                report_data['summary']['warning'] = monitor_data['summary'].get('warning', 0)
                report_data['summary']['error'] = monitor_data['summary'].get('error', 0)
            if 'resorts' in monitor_data:
                report_data['resorts'] = monitor_data['resorts']
        
        print(f"📊 报告数据: {len(report_data.get('resorts', []))} 个雪场, {len(report_data.get('collection_failures', []))} 个失败")
        
        # 保存 JSON 到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as json_file:
            json.dump(report_data, json_file, ensure_ascii=False, indent=2)
            json_path = json_file.name
        
        # 使用临时文件作为 HTML 输出
        html_path = json_path.replace('.json', '.html')
        
        # 使用本地的 generate_html_report 函数生成 HTML
        generate_monitor_html(json_path, html_path)
        
        # 读取生成的 HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 删除临时文件
        os.unlink(json_path)
        os.unlink(html_path)
        
        # 上传报告
        timestamp = stats['start_time'].strftime('%Y%m%d_%H%M%S')
        filename = f"report_{timestamp}.html"
        report_url = uploader.upload_report(html_content, filename)
        print(f"✅ 报告已生成: {report_url}")
        
        # 更新索引
        uploader.update_index()
        print(f"✅ 索引页面已更新")
        
        return report_url
    except Exception as e:
        print(f"⚠️  报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None

