#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪道采集报告 HTML 生成器
"""

from datetime import datetime
from typing import Dict, List


def generate_trails_html_report(report_data: Dict, output_file: str):
    """
    生成雪道采集报告的 HTML 文件
    
    Args:
        report_data: 报告数据字典
        output_file: 输出 HTML 文件路径
    """
    summary = report_data.get('summary', {})
    resorts = report_data.get('resorts', [])
    timestamp = report_data.get('timestamp', '')
    
    # 格式化时间戳
    try:
        dt = datetime.fromisoformat(timestamp)
        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        formatted_time = timestamp
    
    # 计算成功率
    total = summary.get('total', 0)
    success = summary.get('success', 0)
    failed = summary.get('failed', 0)
    skipped = summary.get('skipped', 0)
    success_rate = (success / total * 100) if total > 0 else 0
    
    # 开始构建 HTML
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪道数据采集报告 - {formatted_time}</title>
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
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            font-size: 32px;
            color: #1a202c;
            margin-bottom: 8px;
        }}
        
        .header .timestamp {{
            color: #718096;
            font-size: 14px;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        
        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-4px);
        }}
        
        .card-title {{
            font-size: 14px;
            color: #718096;
            margin-bottom: 8px;
            font-weight: 500;
        }}
        
        .card-value {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        
        .card.total .card-value {{ color: #4299e1; }}
        .card.success .card-value {{ color: #48bb78; }}
        .card.failed .card-value {{ color: #f56565; }}
        .card.skipped .card-value {{ color: #ed8936; }}
        .card.trails .card-value {{ color: #9f7aea; }}
        
        .progress-bar {{
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 12px;
        }}
        
        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        
        .filters {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .filter-buttons {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        
        .filter-btn {{
            padding: 10px 20px;
            border: 2px solid #e2e8f0;
            background: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        .filter-btn:hover {{
            background: #f7fafc;
        }}
        
        .filter-btn.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        
        .search-box {{
            margin-top: 12px;
        }}
        
        .search-input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .resorts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        
        .resort-card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.2s;
        }}
        
        .resort-card:hover {{
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }}
        
        .resort-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 16px;
        }}
        
        .resort-name {{
            font-size: 18px;
            font-weight: bold;
            color: #1a202c;
            margin-bottom: 4px;
        }}
        
        .resort-meta {{
            font-size: 12px;
            color: #718096;
        }}
        
        .status-badge {{
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
        }}
        
        .status-badge.success {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .status-badge.failed {{
            background: #fed7d7;
            color: #742a2a;
        }}
        
        .status-badge.skipped {{
            background: #feebc8;
            color: #7c2d12;
        }}
        
        .trails-stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-top: 16px;
        }}
        
        .stat-item {{
            background: #f7fafc;
            padding: 12px;
            border-radius: 8px;
        }}
        
        .stat-label {{
            font-size: 12px;
            color: #718096;
            margin-bottom: 4px;
        }}
        
        .stat-value {{
            font-size: 20px;
            font-weight: bold;
            color: #2d3748;
        }}
        
        .error-message {{
            margin-top: 12px;
            padding: 12px;
            background: #fff5f5;
            border-left: 4px solid #f56565;
            border-radius: 4px;
            font-size: 13px;
            color: #742a2a;
        }}
        
        .duration {{
            margin-top: 8px;
            font-size: 12px;
            color: #718096;
        }}
        
        .difficulty-badges {{
            display: flex;
            gap: 8px;
            margin-top: 12px;
            flex-wrap: wrap;
        }}
        
        .difficulty-badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .difficulty-badge.easy {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .difficulty-badge.intermediate {{
            background: #bee3f8;
            color: #2c5282;
        }}
        
        .difficulty-badge.advanced {{
            background: #fbb6ce;
            color: #702459;
        }}
        
        .difficulty-badge.expert {{
            background: #2d3748;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🗺️ 雪道数据采集报告</h1>
            <div class="timestamp">生成时间: {formatted_time}</div>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-cards">
            <div class="card total">
                <div class="card-title">总雪场数</div>
                <div class="card-value">{summary.get('total', 0)}</div>
            </div>
            
            <div class="card success">
                <div class="card-title">✅ 采集成功</div>
                <div class="card-value">{summary.get('success', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {success_rate}%; background: #48bb78;"></div>
                </div>
            </div>
            
            <div class="card failed">
                <div class="card-title">❌ 采集失败</div>
                <div class="card-value">{summary.get('failed', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {(failed / total * 100) if total > 0 else 0}%; background: #f56565;"></div>
                </div>
            </div>
            
            <div class="card skipped">
                <div class="card-title">⏭️ 已有数据</div>
                <div class="card-value">{summary.get('skipped', 0)}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {(skipped / total * 100) if total > 0 else 0}%; background: #ed8936;"></div>
                </div>
            </div>
            
            <div class="card trails">
                <div class="card-title">🎿 总雪道数</div>
                <div class="card-value">{summary.get('total_trails', 0)}</div>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="filters">
            <div class="filter-buttons">
                <button class="filter-btn active" onclick="filterResorts('all')">🏔️ 全部 ({summary.get('total', 0)})</button>
                <button class="filter-btn" onclick="filterResorts('success')">✅ 成功 ({summary.get('success', 0)})</button>
                <button class="filter-btn" onclick="filterResorts('failed')">❌ 失败 ({summary.get('failed', 0)})</button>
                <button class="filter-btn" onclick="filterResorts('skipped')">⏭️ 跳过 ({summary.get('skipped', 0)})</button>
            </div>
            <div class="search-box">
                <input type="text" class="search-input" placeholder="🔍 搜索雪场名称..." onkeyup="searchResorts(this.value)">
            </div>
        </div>
        
        <!-- Resorts Grid -->
        <div class="resorts-grid">
"""
    
    # 添加每个雪场的卡片
    for resort in resorts:
        status = resort.get('status', 'failed')
        status_text = {
            'success': '✅ 成功',
            'failed': '❌ 失败',
            'skipped': '⏭️ 跳过'
        }.get(status, '❓ 未知')
        
        trails_count = resort.get('trails_count', 0)
        boundary_points = resort.get('boundary_points', 0)
        duration = resort.get('duration', 0)
        error = resort.get('error', '')
        
        # 雪道难度统计
        difficulty_stats = resort.get('difficulty_stats', {})
        easy = difficulty_stats.get('easy', 0)
        intermediate = difficulty_stats.get('intermediate', 0)
        advanced = difficulty_stats.get('advanced', 0)
        expert = difficulty_stats.get('expert', 0)
        
        html_content += f"""
            <div class="resort-card" data-status="{status}" data-name="{resort.get('name', '').lower()}">
                <div class="resort-header">
                    <div>
                        <div class="resort-name">{resort.get('name', 'Unknown')}</div>
                        <div class="resort-meta">
                            ID: {resort.get('resort_id', 'N/A')} | {resort.get('location', 'N/A')}
                        </div>
                    </div>
                    <span class="status-badge {status}">{status_text}</span>
                </div>
"""
        
        if status == 'success' or status == 'skipped':
            html_content += f"""
                <div class="trails-stats">
                    <div class="stat-item">
                        <div class="stat-label">🎿 雪道数量</div>
                        <div class="stat-value">{trails_count}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">📐 边界点数</div>
                        <div class="stat-value">{boundary_points}</div>
                    </div>
                </div>
"""
            
            # 难度分布
            if easy > 0 or intermediate > 0 or advanced > 0 or expert > 0:
                html_content += f"""
                <div class="difficulty-badges">
                    {'<span class="difficulty-badge easy">🟢 初级: ' + str(easy) + '</span>' if easy > 0 else ''}
                    {'<span class="difficulty-badge intermediate">🔵 中级: ' + str(intermediate) + '</span>' if intermediate > 0 else ''}
                    {'<span class="difficulty-badge advanced">⚫ 高级: ' + str(advanced) + '</span>' if advanced > 0 else ''}
                    {'<span class="difficulty-badge expert">💎 专家: ' + str(expert) + '</span>' if expert > 0 else ''}
                </div>
"""
        
        if error:
            html_content += f"""
                <div class="error-message">
                    ❌ {error}
                </div>
"""
        
        if duration > 0:
            html_content += f"""
                <div class="duration">⏱️ 耗时: {duration:.1f} 秒</div>
"""
        
        html_content += """
            </div>
"""
    
    # 添加 JavaScript 和结束标签
    html_content += """
        </div>
    </div>
    
    <script>
        function filterResorts(status) {
            const cards = document.querySelectorAll('.resort-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            // 更新按钮状态
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // 过滤卡片
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
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"[OK] HTML 报告已生成: {output_file}")


