#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S3 报告上传器（简化版）
只负责上传报告到 S3 和更新索引
"""

import boto3
import os
from datetime import datetime, timezone
from typing import List, Dict
import pytz


class S3ReportUploader:
    """S3 报告上传器"""
    
    def __init__(self, bucket_name: str = None):
        """
        初始化上传器
        
        Args:
            bucket_name: S3 bucket 名称
        """
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name or os.environ.get('REPORTS_BUCKET', 'resort-data-reports')
        self.la_tz = pytz.timezone('America/Los_Angeles')
    
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

