#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda 采集报告生成器（详细版）
生成包含数据质量监控的详细 HTML 报告并上传到 S3
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Optional
import os
import pytz


class CollectionReportGenerator:
    """采集报告生成器（详细版）"""
    
    def __init__(self, bucket_name: str = None):
        """
        初始化报告生成器
        
        Args:
            bucket_name: S3 bucket 名称
        """
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name or os.environ.get('REPORTS_BUCKET', 'resort-data-reports')
        self.la_tz = pytz.timezone('America/Los_Angeles')
    
    def to_la_time(self, dt: datetime) -> str:
        """转换为洛杉矶时间"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        la_time = dt.astimezone(self.la_tz)
        return la_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    def generate_report_with_monitoring(self, stats: Dict, monitor_data: Optional[Dict] = None) -> str:
        """
        生成包含数据质量监控的详细报告
        
        Args:
            stats: 采集统计数据
            monitor_data: 监控报告数据（来自 monitor.py）
        
        Returns:
            HTML 字符串
        """
        start_time = stats.get('start_time')
        end_time = stats.get('end_time')
        duration = (end_time - start_time).total_seconds()
        
        total = stats.get('total_resorts', 0)
        success = stats.get('success_count', 0)
        failed = stats.get('fail_count', 0)
        success_rate = (success / total * 100) if total > 0 else 0
        
        failed_resorts = stats.get('failed_resorts', [])
        
        # 洛杉矶时间
        start_time_la = self.to_la_time(start_time)
        end_time_la = self.to_la_time(end_time)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪场数据采集报告 - {start_time_la}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 32px;
            color: #2d3748;
            margin-bottom: 10px;
        }}
        
        .header .time {{
            color: #718096;
            font-size: 14px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        
        .stat-card .label {{
            color: #718096;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #2d3748;
        }}
        
        .stat-card.success .value {{ color: #48bb78; }}
        .stat-card.error .value {{ color: #f56565; }}
        .stat-card.warning .value {{ color: #ed8936; }}
        
        .section {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        
        .section h2 {{
            color: #2d3748;
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
        }}
        
        .progress-bar {{
            height: 10px;
            background: #e2e8f0;
            border-radius: 5px;
            overflow: hidden;
            margin: 15px 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #48bb78 0%, #38a169 100%);
        }}
        
        .quality-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .quality-item {{
            padding: 15px;
            background: #f7fafc;
            border-radius: 8px;
            border-left: 4px solid #48bb78;
        }}
        
        .quality-item.warning {{ border-left-color: #ed8936; }}
        .quality-item.error {{ border-left-color: #f56565; }}
        
        .quality-item .label {{
            color: #718096;
            font-size: 13px;
            margin-bottom: 5px;
        }}
        
        .quality-item .percentage {{
            font-size: 24px;
            font-weight: bold;
            color: #2d3748;
        }}
        
        .failed-list {{
            list-style: none;
        }}
        
        .failed-item {{
            padding: 15px;
            margin-bottom: 10px;
            background: #fff5f5;
            border-left: 4px solid #f56565;
            border-radius: 4px;
        }}
        
        .failed-item .resort-name {{
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 5px;
        }}
        
        .failed-item .error-msg {{
            color: #718096;
            font-size: 13px;
        }}
        
        .monitor-details {{
            margin-top: 20px;
        }}
        
        .monitor-item {{
            padding: 12px;
            margin-bottom: 8px;
            background: #f7fafc;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .monitor-item .label {{
            color: #4a5568;
            font-size: 14px;
        }}
        
        .monitor-item .value {{
            font-weight: 600;
            color: #2d3748;
        }}
        
        .back-link {{
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            transition: background 0.3s;
        }}
        
        .back-link:hover {{
            background: #5a67d8;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .badge.success {{ background: #c6f6d5; color: #22543d; }}
        .badge.warning {{ background: #feebc8; color: #7c2d12; }}
        .badge.error {{ background: #fed7d7; color: #742a2a; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏔️ 雪场数据采集报告</h1>
            <div class="time">
                📅 采集时间: {start_time_la} - {end_time_la.split()[-2]}<br>
                ⏱️ 执行时长: {int(duration // 60)} 分 {int(duration % 60)} 秒
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">📊 总雪场数</div>
                <div class="value">{total}</div>
            </div>
            
            <div class="stat-card success">
                <div class="label">✅ 采集成功</div>
                <div class="value">{success}</div>
            </div>
            
            <div class="stat-card error">
                <div class="label">❌ 采集失败</div>
                <div class="value">{failed}</div>
            </div>
            
            <div class="stat-card">
                <div class="label">📈 成功率</div>
                <div class="value">{success_rate:.1f}%</div>
            </div>
        </div>
        
        <div class="section">
            <h2>采集进度</h2>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {success_rate}%"></div>
            </div>
            <p style="color: #718096; text-align: center;">
                {success} / {total} 个雪场采集成功
            </p>
        </div>
"""
        
        # 数据质量监控部分
        if monitor_data:
            html += self._generate_monitoring_section(monitor_data)
        
        # 失败详情
        if failed_resorts:
            # 按错误类型分组
            errors_by_type = {}
            for resort in failed_resorts:
                error = resort.get('error', 'Unknown error')
                # 简化错误类型
                error_type = 'UNKNOWN'
                if 'NO_DATA' in error or '采集器返回空数据' in error:
                    error_type = 'NO_DATA'
                elif 'connection' in error.lower() or 'concurrent operations' in error:
                    error_type = 'CONNECTION_ERROR'
                elif 'timeout' in error.lower():
                    error_type = 'TIMEOUT'
                elif 'HTTP' in error:
                    error_type = 'HTTP_ERROR'
                
                if error_type not in errors_by_type:
                    errors_by_type[error_type] = []
                errors_by_type[error_type].append(resort)
            
            html += """
        <div class="section">
            <h2>❌ 失败详情</h2>
"""
            for error_type, resorts in errors_by_type.items():
                html += f"""
            <h3 style="color: #4a5568; margin: 20px 0 10px 0;">{error_type}: {len(resorts)} 个</h3>
            <ul class="failed-list">
"""
                for resort in resorts[:10]:  # 每种类型最多显示10个
                    html += f"""
                <li class="failed-item">
                    <div class="resort-name">{resort.get('name', 'Unknown')}</div>
                    <div class="error-msg">{resort.get('error', 'Unknown error')[:200]}</div>
                </li>
"""
                if len(resorts) > 10:
                    html += f"""
                <li style="padding: 10px; color: #718096; text-align: center;">
                    ...还有 {len(resorts) - 10} 个雪场
                </li>
"""
                html += """
            </ul>
"""
            html += """
        </div>
"""
        
        html += """
        <div style="text-align: center;">
            <a href="/" class="back-link">← 返回报告列表</a>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _generate_monitoring_section(self, monitor_data: Dict) -> str:
        """生成数据质量监控部分的 HTML"""
        summary = monitor_data.get('summary', {})
        resorts = monitor_data.get('resorts', [])
        
        total_checked = summary.get('total_resorts', 0)
        good_count = summary.get('status_counts', {}).get('good', 0)
        warning_count = summary.get('status_counts', {}).get('warning', 0)
        error_count = summary.get('status_counts', {}).get('error', 0)
        
        html = f"""
        <div class="section">
            <h2>📊 数据质量监控</h2>
            
            <div class="quality-grid">
                <div class="quality-item">
                    <div class="label">✅ 数据完整</div>
                    <div class="percentage">{good_count}</div>
                </div>
                <div class="quality-item warning">
                    <div class="label">⚠️ 数据警告</div>
                    <div class="percentage">{warning_count}</div>
                </div>
                <div class="quality-item error">
                    <div class="label">❌ 数据异常</div>
                    <div class="percentage">{error_count}</div>
                </div>
                <div class="quality-item">
                    <div class="label">📈 数据质量率</div>
                    <div class="percentage">{(good_count/total_checked*100) if total_checked > 0 else 0:.1f}%</div>
                </div>
            </div>
            
            <div class="monitor-details">
                <h3 style="color: #4a5568; margin: 20px 0 10px 0;">字段完整度</h3>
"""
        
        # 字段统计
        field_stats = summary.get('field_stats', {})
        for field, stats in list(field_stats.items())[:10]:  # 显示前10个字段
            total = stats.get('total', 0)
            present = stats.get('present', 0)
            percentage = (present / total * 100) if total > 0 else 0
            
            badge_class = 'success' if percentage > 90 else ('warning' if percentage > 70 else 'error')
            
            html += f"""
                <div class="monitor-item">
                    <span class="label">{field}</span>
                    <span><span class="badge {badge_class}">{percentage:.1f}%</span> ({present}/{total})</span>
                </div>
"""
        
        html += """
            </div>
        </div>
"""
        
        return html
    
    def generate_report_html(self, stats: Dict) -> str:
        """
        生成采集报告 HTML（兼容旧接口）
        
        Args:
            stats: 采集统计数据
        
        Returns:
            HTML 字符串
        """
        return self.generate_report_with_monitoring(stats, None)
    
    def upload_report(self, html_content: str, filename: str) -> str:
        """
        上传报告到 S3
        
        Args:
            html_content: HTML 内容
            filename: 文件名
        
        Returns:
            S3 URL
        """
        key = f"reports/{filename}"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=html_content.encode('utf-8'),
            ContentType='text/html',
            CacheControl='max-age=300'
        )
        
        return f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
    
    def list_reports(self) -> List[Dict]:
        """
        列出所有报告
        
        Returns:
            报告列表
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='reports/',
                MaxKeys=1000
            )
            
            reports = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.html') and key != 'reports/latest.html':
                    # 从文件名解析时间: report_20251110_120000.html
                    filename = key.split('/')[-1]
                    try:
                        timestamp_str = filename.replace('report_', '').replace('.html', '')
                        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        # 转换为洛杉矶时间
                        timestamp_utc = timestamp.replace(tzinfo=timezone.utc)
                        timestamp_la = timestamp_utc.astimezone(self.la_tz)
                        reports.append({
                            'filename': filename,
                            'timestamp': timestamp_la,
                            'key': key
                        })
                    except:
                        continue
            
            return reports
        except Exception as e:
            print(f"列出报告失败: {e}")
            return []
    
    def generate_index_html(self, reports: List[Dict]) -> str:
        """生成报告列表页面"""
        reports_html = ""
        for report in sorted(reports, key=lambda x: x['timestamp'], reverse=True):
            timestamp = report['timestamp']
            filename = report['filename']
            
            reports_html += f"""
                <div class="report-card">
                    <div class="report-icon">📊</div>
                    <div class="report-info">
                        <div class="report-date">{timestamp.strftime('%Y-%m-%d')}</div>
                        <div class="report-time">{timestamp.strftime('%H:%M:%S %Z')}</div>
                    </div>
                    <a href="/reports/{filename}" class="view-btn">查看报告 →</a>
                </div>
"""
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪场数据采集报告列表</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .header h1 {{ font-size: 36px; color: #2d3748; margin-bottom: 10px; }}
        .header p {{ color: #718096; font-size: 16px; }}
        .reports-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        .report-card {{
            background: white;
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 15px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .report-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 50px rgba(0,0,0,0.15);
        }}
        .report-icon {{ font-size: 40px; }}
        .report-info {{ flex: 1; }}
        .report-date {{ font-size: 18px; font-weight: bold; color: #2d3748; margin-bottom: 5px; }}
        .report-time {{ font-size: 14px; color: #718096; }}
        .view-btn {{
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.3s ease;
            white-space: nowrap;
        }}
        .view-btn:hover {{ background: #5a67d8; }}
        .empty-state {{
            background: white;
            border-radius: 16px;
            padding: 60px 40px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .empty-state .icon {{ font-size: 80px; margin-bottom: 20px; }}
        .empty-state h2 {{ color: #2d3748; font-size: 24px; margin-bottom: 10px; }}
        .empty-state p {{ color: #718096; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏔️ 雪场数据采集报告</h1>
            <p>查看历史采集报告，了解数据采集情况（洛杉矶时间）</p>
        </div>
        
        <div class="reports-grid">
{reports_html if reports_html else '''
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="icon">📭</div>
                <h2>暂无报告</h2>
                <p>还没有生成任何采集报告</p>
            </div>
'''}
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def update_index(self):
        """更新索引页面"""
        reports = self.list_reports()
        index_html = self.generate_index_html(reports)
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key='index.html',
            Body=index_html.encode('utf-8'),
            ContentType='text/html',
            CacheControl='max-age=300'
        )
        
        print(f"✅ 索引页面已更新，共 {len(reports)} 个报告")
