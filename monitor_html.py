#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 HTML 监控报告
"""

import json
from datetime import datetime
from pathlib import Path


def generate_html_report(json_report_file: str, html_output_file: str):
    """
    从 JSON 报告生成 HTML 页面
    
    Args:
        json_report_file: JSON 报告文件路径
        html_output_file: HTML 输出文件路径
    """
    # 读取 JSON 报告
    try:
        with open(json_report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] 报告文件不存在: {json_report_file}")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] 报告文件解析失败: {e}")
        return
    
    summary = report_data.get('summary', {})
    resorts = report_data.get('resorts', [])
    collection_failures = report_data.get('collection_failures', [])
    timestamp = report_data.get('timestamp', '')
    duration_seconds = report_data.get('duration_seconds', 0)
    
    # 格式化时间
    try:
        dt = datetime.fromisoformat(timestamp)
        formatted_time = dt.strftime('%Y年%m月%d日 %H:%M:%S')
    except:
        formatted_time = timestamp
    
    # 格式化运行时长
    if duration_seconds > 0:
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        if minutes > 0:
            duration_str = f" | ⏱️ 执行时长: {minutes} 分 {seconds} 秒"
        else:
            duration_str = f" | ⏱️ 执行时长: {seconds} 秒"
    else:
        duration_str = ""
    
    # 生成 HTML
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
        
        @media (max-width: 768px) {{
            .resorts-grid {{
                grid-template-columns: 1fr;
            }}
            
            .filter-buttons {{
                flex-wrap: wrap;
            }}
            
            .search-box {{
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>
                <span>❄️</span>
                雪场数据监控报告
            </h1>
            <div class="subtitle">
                最后更新: {formatted_time}{duration_str}
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-cards">
            <div class="card">
                <div class="card-title">总雪场数</div>
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
                <div class="card-title">平均数据完整度</div>
                <div class="card-value" style="color: #667eea;">{summary.get('avg_score', 0):.1f}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('avg_score', 0)}%; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);"></div>
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
                value_str = check.get('value', '')
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
            fail_time = dt.strftime('%H:%M:%S')
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
                        <span class="check-label">{error_message}</span>
                    </div>
                    <div class="check-item error" style="word-break: break-all;">
                        <span class="check-icon">🔗</span>
                        <span class="check-label" style="font-size: 12px;">{url}</span>
                    </div>
                </div>
            </div>
"""
    
    # 结束 HTML
    html_content += """
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
        
        // Auto-refresh every 5 minutes
        setTimeout(() => {
            location.reload();
        }, 5 * 60 * 1000);
    </script>
</body>
</html>
"""
    
    # 写入文件
    Path(html_output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(html_output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"[OK] HTML 报告已生成: {html_output_file}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='生成 HTML 监控报告')
    parser.add_argument(
        '--json',
        default='data/monitor_report.json',
        help='JSON 报告文件路径'
    )
    parser.add_argument(
        '--output',
        default='data/monitor_report.html',
        help='HTML 输出文件路径'
    )
    
    args = parser.parse_args()
    
    generate_html_report(args.json, args.output)

