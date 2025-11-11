#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda 采集报告生成器
生成 HTML 报告并上传到 S3
"""

import json
import boto3
from datetime import datetime
from typing import Dict, List
import os


class CollectionReportGenerator:
    """采集报告生成器"""
    
    def __init__(self, bucket_name: str = None):
        """
        初始化报告生成器
        
        Args:
            bucket_name: S3 bucket 名称
        """
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name or os.environ.get('REPORTS_BUCKET', 'resort-data-reports')
        
    def generate_report_html(self, stats: Dict) -> str:
        """
        生成采集报告 HTML
        
        Args:
            stats: 采集统计数据
                {
                    'start_time': datetime,
                    'end_time': datetime,
                    'total_resorts': int,
                    'success_count': int,
                    'fail_count': int,
                    'failed_resorts': [{'name': str, 'error': str}, ...],
                    'data_quality': {...}
                }
        
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
        data_quality = stats.get('data_quality', {})
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪场数据采集报告 - {start_time.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
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
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-card .label {{
            color: #718096;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            font-size: 36px;
            font-weight: bold;
            color: #2d3748;
        }}
        
        .stat-card.success .value {{
            color: #48bb78;
        }}
        
        .stat-card.error .value {{
            color: #f56565;
        }}
        
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
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #48bb78 0%, #38a169 100%);
            transition: width 1s ease;
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
            font-size: 14px;
        }}
        
        .quality-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .quality-item {{
            padding: 15px;
            background: #f7fafc;
            border-radius: 8px;
        }}
        
        .quality-item .label {{
            color: #718096;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        
        .quality-item .percentage {{
            font-size: 24px;
            font-weight: bold;
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
            transition: background 0.3s ease;
        }}
        
        .back-link:hover {{
            background: #5a67d8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏔️ 雪场数据采集报告</h1>
            <div class="time">
                📅 采集时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%H:%M:%S')}<br>
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
        
        # 失败详情
        if failed_resorts:
            html += """
        <div class="section">
            <h2>❌ 失败详情</h2>
            <ul class="failed-list">
"""
            for resort in failed_resorts:
                html += f"""
                <li class="failed-item">
                    <div class="resort-name">{resort.get('name', 'Unknown')}</div>
                    <div class="error-msg">{resort.get('error', 'Unknown error')}</div>
                </li>
"""
            html += """
            </ul>
        </div>
"""
        
        # 数据质量
        if data_quality:
            html += """
        <div class="section">
            <h2>📊 数据质量</h2>
            <div class="quality-grid">
"""
            for key, value in data_quality.items():
                label = key.replace('_', ' ').title()
                html += f"""
                <div class="quality-item">
                    <div class="label">{label}</div>
                    <div class="percentage">{value}%</div>
                </div>
"""
            html += """
            </div>
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
    
    def generate_index_html(self, reports: List[Dict]) -> str:
        """
        生成报告列表页面
        
        Args:
            reports: 报告列表
                [{'filename': str, 'timestamp': datetime, 'url': str}, ...]
        
        Returns:
            HTML 字符串
        """
        reports_html = ""
        for report in sorted(reports, key=lambda x: x['timestamp'], reverse=True):
            timestamp = report['timestamp']
            filename = report['filename']
            
            reports_html += f"""
                <div class="report-card">
                    <div class="report-icon">📊</div>
                    <div class="report-info">
                        <div class="report-date">{timestamp.strftime('%Y-%m-%d')}</div>
                        <div class="report-time">{timestamp.strftime('%H:%M:%S')}</div>
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
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 36px;
            color: #2d3748;
            margin-bottom: 10px;
        }}
        
        .header p {{
            color: #718096;
            font-size: 16px;
        }}
        
        .filters {{
            background: white;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .filters input {{
            flex: 1;
            min-width: 200px;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }}
        
        .filters input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
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
        
        .report-icon {{
            font-size: 40px;
        }}
        
        .report-info {{
            flex: 1;
        }}
        
        .report-date {{
            font-size: 18px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 5px;
        }}
        
        .report-time {{
            font-size: 14px;
            color: #718096;
        }}
        
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
        
        .view-btn:hover {{
            background: #5a67d8;
        }}
        
        .empty-state {{
            background: white;
            border-radius: 16px;
            padding: 60px 40px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        
        .empty-state .icon {{
            font-size: 80px;
            margin-bottom: 20px;
        }}
        
        .empty-state h2 {{
            color: #2d3748;
            font-size: 24px;
            margin-bottom: 10px;
        }}
        
        .empty-state p {{
            color: #718096;
        }}
    </style>
    <script>
        function filterReports() {{
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const cards = document.querySelectorAll('.report-card');
            
            cards.forEach(card => {{
                const date = card.querySelector('.report-date').textContent.toLowerCase();
                const time = card.querySelector('.report-time').textContent.toLowerCase();
                const text = date + ' ' + time;
                
                if (text.includes(searchTerm)) {{
                    card.style.display = 'flex';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏔️ 雪场数据采集报告</h1>
            <p>查看历史采集报告，了解数据采集情况</p>
        </div>
        
        <div class="filters">
            <input 
                type="text" 
                id="search" 
                placeholder="🔍 搜索报告 (例如: 2025-11-10)" 
                onkeyup="filterReports()"
            >
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
                        reports.append({
                            'filename': filename,
                            'timestamp': timestamp,
                            'key': key
                        })
                    except:
                        continue
            
            return reports
        except Exception as e:
            print(f"列出报告失败: {e}")
            return []
    
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

