#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda 采集报告生成器（完整监控版）
使用本地 monitor_html.py 的逻辑生成详细报告
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Optional
import os
import pytz


class CollectionReportGenerator:
    """采集报告生成器（完整监控版）"""
    
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
    
    def generate_html_report(self, report_data: Dict) -> str:
        """
        生成完整的监控 HTML 报告（与本地 monitor_html.py 一致）
        
        Args:
            report_data: 完整的监控报告数据
                {
                    'timestamp': str,
                    'summary': {...},
                    'resorts': [...],
                    'collection_failures': [...]
                }
        
        Returns:
            HTML 字符串
        """
        summary = report_data.get('summary', {})
        resorts = report_data.get('resorts', [])
        collection_failures = report_data.get('collection_failures', [])
        timestamp = report_data.get('timestamp', '')
        
        # 格式化时间（洛杉矶时间）
        try:
            dt = datetime.fromisoformat(timestamp)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            la_time = dt.astimezone(self.la_tz)
            formatted_time = la_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        except:
            formatted_time = timestamp
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪场数据监控报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        .header h1 {{
            color: #2d3748;
            font-size: 36px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        
        .header .subtitle {{
            color: #718096;
            font-size: 16px;
            margin-top: 8px;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
        }}
        
        .card-title {{
            color: #718096;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .card-value {{
            font-size: 36px;
            font-weight: bold;
            color: #2d3748;
        }}
        
        .card.success .card-value {{ color: #48bb78; }}
        .card.warning .card-value {{ color: #ed8936; }}
        .card.error .card-value {{ color: #f56565; }}
        
        .progress-bar {{
            width: 100%;
            height: 10px;
            background: #e2e8f0;
            border-radius: 5px;
            overflow: hidden;
            margin-top: 15px;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #48bb78 0%, #38a169 100%);
            transition: width 0.5s;
        }}
        
        .resorts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }}
        
        .resort-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .resort-card.success {{
            border-left: 5px solid #48bb78;
        }}
        
        .resort-card.warning {{
            border-left: 5px solid #ed8936;
        }}
        
        .resort-card.error {{
            border-left: 5px solid #f56565;
        }}
        
        .resort-card.failed {{
            border-left: 5px solid #c53030;
            background: linear-gradient(135deg, #ffffff 0%, #fff5f5 100%);
        }}
        
        .resort-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}
        
        .resort-name {{
            font-size: 20px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 5px;
        }}
        
        .resort-meta {{
            font-size: 13px;
            color: #718096;
        }}
        
        .status-badge {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .status-badge.success {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .status-badge.warning {{
            background: #feebc8;
            color: #7c2d12;
        }}
        
        .status-badge.error {{
            background: #fed7d7;
            color: #742a2a;
        }}
        
        .score-display {{
            text-align: center;
            margin: 20px 0;
        }}
        
        .score-circle {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            color: white;
            margin: 0 auto;
        }}
        
        .score-circle.high {{ background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); }}
        .score-circle.medium {{ background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%); }}
        .score-circle.low {{ background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%); }}
        
        .checks-list {{
            margin-top: 15px;
        }}
        
        .check-item {{
            padding: 8px 12px;
            margin: 5px 0;
            border-radius: 6px;
            font-size: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .check-item.success {{
            background: #f0fdf4;
            color: #166534;
        }}
        
        .check-item.warning {{
            background: #fffbeb;
            color: #92400e;
        }}
        
        .check-item.error {{
            background: #fef2f2;
            color: #991b1b;
        }}
        
        .check-icon {{
            margin-right: 8px;
        }}
        
        .check-label {{
            flex: 1;
        }}
        
        .check-value {{
            font-weight: 600;
            margin-left: 10px;
        }}
        
        .filter-buttons {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            flex-wrap: wrap;
        }}
        
        .filter-btn {{
            padding: 10px 20px;
            border: 2px solid #e2e8f0;
            background: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .filter-btn:hover {{
            border-color: #667eea;
            color: #667eea;
        }}
        
        .filter-btn.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        
        .search-box {{
            flex: 1;
            min-width: 200px;
            padding: 10px 15px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }}
        
        .search-box:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .back-link {{
            display: inline-block;
            margin-top: 30px;
            padding: 12px 24px;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .back-link:hover {{
            background: #667eea;
            color: white;
            transform: translateY(-2px);
        }}
        
        @media (max-width: 768px) {{
            .resorts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>
                <span>🏔️</span>
                雪场数据采集报告
            </h1>
            <div class="subtitle">
                📅 采集时间: {formatted_time}
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-cards">
            <div class="card">
                <div class="card-title">📊 总雪场数</div>
                <div class="card-value">{summary.get('collection_total', summary.get('total', 0))}</div>
            </div>
            
            <div class="card success">
                <div class="card-title">✅ 采集成功</div>
                <div class="card-value">{summary.get('collection_success', summary.get('total', 0))}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('collection_success', summary.get('total', 0)) / max(summary.get('collection_total', summary.get('total', 1)), 1) * 100}%; background: #48bb78;"></div>
                </div>
            </div>
            
            <div class="card error">
                <div class="card-title">❌ 采集失败</div>
                <div class="card-value">{summary.get('collection_failed', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('collection_failed', 0) / max(summary.get('collection_total', summary.get('total', 1)), 1) * 100}%; background: #f56565;"></div>
                </div>
            </div>
            
            <div class="card success">
                <div class="card-title">✅ 数据完整</div>
                <div class="card-value">{summary.get('success', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('success', 0) / max(summary.get('collection_success', summary.get('total', 1)), 1) * 100}%; background: #48bb78;"></div>
                </div>
            </div>
            
            <div class="card warning">
                <div class="card-title">⚠️ 数据不完整</div>
                <div class="card-value">{summary.get('warning', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('warning', 0) / max(summary.get('collection_success', summary.get('total', 1)), 1) * 100}%; background: #ed8936;"></div>
                </div>
            </div>
            
            <div class="card error">
                <div class="card-title">❌ 数据错误</div>
                <div class="card-value">{summary.get('error', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('error', 0) / max(summary.get('collection_success', summary.get('total', 1)), 1) * 100}%; background: #f56565;"></div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">📈 成功率</div>
                <div class="card-value" style="color: #667eea;">{(summary.get('collection_success', 0) / max(summary.get('collection_total', 1), 1) * 100):.1f}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {(summary.get('collection_success', 0) / max(summary.get('collection_total', 1), 1) * 100)}%; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);"></div>
                </div>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterResorts('all')">全部 ({summary.get('collection_total', summary.get('total', 0))})</button>
            <button class="filter-btn" onclick="filterResorts('success')">✅ 正常 ({summary.get('success', 0)})</button>
            <button class="filter-btn" onclick="filterResorts('warning')">⚠️ 警告 ({summary.get('warning', 0)})</button>
            <button class="filter-btn" onclick="filterResorts('error')">❌ 错误 ({summary.get('error', 0)})</button>
            <button class="filter-btn" onclick="filterResorts('failed')">🚫 采集失败 ({summary.get('collection_failed', 0)})</button>
            <input type="text" class="search-box" placeholder="搜索雪场名称..." onkeyup="searchResorts(this.value)">
        </div>
        
        <!-- Resorts Grid -->
        <div class="resorts-grid" id="resorts-grid">
"""
        
        # 生成每个雪场的卡片
        for resort in sorted(resorts, key=lambda r: r.get('score', 0)):
            status = resort.get('overall_status', 'success')
            score = resort.get('score', 0)
            
            # 确定分数等级
            if score >= 80:
                score_class = 'high'
            elif score >= 50:
                score_class = 'medium'
            else:
                score_class = 'low'
            
            # 状态图标
            status_icons = {
                'success': '✅',
                'warning': '⚠️',
                'error': '❌'
            }
            status_icon = status_icons.get(status, '❓')
            
            html_content += f"""
            <div class="resort-card {status}" data-status="{status}" data-name="{resort.get('resort_name', '').lower()}">
                <div class="resort-header">
                    <div>
                        <div class="resort-name">{resort.get('resort_name', 'Unknown')}</div>
                        <div class="resort-meta">
                            ID: {resort.get('resort_id', 'N/A')} | 数据源: {resort.get('data_source', 'N/A')}
                        </div>
                    </div>
                    <span class="status-badge {status}">{status_icon} {status.upper()}</span>
                </div>
                
                <div class="score-display">
                    <div class="score-circle {score_class}">{score:.0f}%</div>
                </div>
                
                <div class="checks-list">
"""
            
            # 只显示有问题的检查项
            checks = resort.get('checks', [])
            problem_checks = [c for c in checks if c.get('status') in ['error', 'warning']]
            
            if problem_checks:
                for check in problem_checks[:10]:  # 最多显示10个问题
                    check_status = check.get('status', 'success')
                    check_icon = status_icons.get(check_status, '•')
                    value_str = str(check.get('value', ''))
                    if value_str and value_str != 'None':
                        value_display = f"<span class='check-value'>{value_str}</span>"
                    else:
                        value_display = ""
                    
                    html_content += f"""
                    <div class="check-item {check_status}">
                        <span class="check-icon">{check_icon}</span>
                        <span class="check-label">{check.get('field', 'Unknown')}: {check.get('message', '')}</span>
                        {value_display}
                    </div>
"""
            else:
                html_content += """
                    <div class="check-item success">
                        <span class="check-icon">✅</span>
                        <span class="check-label">所有数据检查通过</span>
                    </div>
"""
            
            html_content += """
                </div>
            </div>
"""
        
        # 添加采集失败的雪场卡片
        for failure in collection_failures:
            error_type = failure.get('error_type', 'UNKNOWN')
            error_message = failure.get('error_message', '未知错误')
            url = failure.get('url', 'N/A')
            timestamp_str = failure.get('timestamp', '')
            
            # 格式化时间
            try:
                dt = datetime.fromisoformat(timestamp_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                la_time = dt.astimezone(self.la_tz)
                fail_time = la_time.strftime('%H:%M:%S')
            except:
                fail_time = timestamp_str
            
            # 错误类型对应的图标和说明
            error_type_map = {
                'HTTP_404': ('🔗', '页面不存在 (404)'),
                'TIMEOUT': ('⏱️', '请求超时'),
                'CONNECTION_ERROR': ('📡', '连接错误'),
                'JSON_ERROR': ('📄', 'JSON解析错误'),
                'NO_DATA': ('📭', '无数据返回'),
                'UNKNOWN': ('❓', '未知错误')
            }
            
            error_icon, error_title = error_type_map.get(error_type, ('❓', error_type))
            
            html_content += f"""
            <div class="resort-card failed" data-status="failed" data-name="{failure.get('resort_name', '').lower()}">
                <div class="resort-header">
                    <div>
                        <div class="resort-name">{failure.get('resort_name', 'Unknown')}</div>
                        <div class="resort-meta">
                            ID: {failure.get('resort_id', 'N/A')} | 失败时间: {fail_time}
                        </div>
                    </div>
                    <span class="status-badge error">🚫 采集失败</span>
                </div>
                
                <div class="score-display">
                    <div class="score-circle low">{error_icon}</div>
                </div>
                
                <div class="checks-list">
                    <div class="check-item error">
                        <span class="check-icon">❌</span>
                        <span class="check-label"><strong>{error_title}</strong></span>
                    </div>
                    <div class="check-item error">
                        <span class="check-icon">💬</span>
                        <span class="check-label">{error_message[:200]}</span>
                    </div>
                    <div class="check-item error" style="word-break: break-all;">
                        <span class="check-icon">🔗</span>
                        <span class="check-label" style="font-size: 12px;">{url[:100]}</span>
                    </div>
                </div>
            </div>
"""
        
        # 结束 HTML
        html_content += """
        </div>
        
        <div style="text-align: center;">
            <a href="/" class="back-link">← 返回报告列表</a>
        </div>
    </div>
    
    <script>
        function filterResorts(status) {
            const cards = document.querySelectorAll('.resort-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            // Update active button
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Filter cards
            cards.forEach(card => {
                if (status === 'all' || card.dataset.status === status) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
        
        function searchResorts(query) {
            const cards = document.querySelectorAll('.resort-card');
            const searchTerm = query.toLowerCase();
            
            cards.forEach(card => {
                const name = card.dataset.name;
                if (name.includes(searchTerm)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
"""
        
        return html_content
    
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
