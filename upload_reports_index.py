#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成并上传报告主页到 S3
"""

import boto3
from datetime import datetime
import os

def generate_index_html():
    """生成报告列表主页"""
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>雪场数据采集报告</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .header h1 {
            font-size: 36px;
            color: #2d3748;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #718096;
            font-size: 16px;
        }
        
        .filters {
            background: white;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .filters input {
            flex: 1;
            min-width: 200px;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        .filters input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .reports-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .report-card {
            background: white;
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 15px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .report-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 50px rgba(0,0,0,0.15);
        }
        
        .report-icon {
            font-size: 40px;
        }
        
        .report-info {
            flex: 1;
        }
        
        .report-date {
            font-size: 18px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 5px;
        }
        
        .report-time {
            font-size: 14px;
            color: #718096;
        }
        
        .view-btn {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.3s ease;
            white-space: nowrap;
        }
        
        .view-btn:hover {
            background: #5a67d8;
        }
        
        .empty-state {
            background: white;
            border-radius: 16px;
            padding: 60px 40px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        
        .empty-state .icon {
            font-size: 80px;
            margin-bottom: 20px;
        }
        
        .empty-state h2 {
            color: #2d3748;
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .empty-state p {
            color: #718096;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 18px;
        }
    </style>
    <script>
        // 从 S3 加载报告列表
        async function loadReports() {
            const reportsGrid = document.getElementById('reportsGrid');
            
            try {
                // 这里会被后端脚本替换为实际的报告列表
                const reports = [];
                
                if (reports.length === 0) {
                    reportsGrid.innerHTML = `
                        <div class="empty-state" style="grid-column: 1 / -1;">
                            <div class="icon">📭</div>
                            <h2>暂无报告</h2>
                            <p>还没有生成任何采集报告</p>
                            <p style="margin-top: 20px; font-size: 14px;">首次 Lambda 采集完成后，报告将自动出现在这里</p>
                        </div>
                    `;
                } else {
                    reportsGrid.innerHTML = reports.map(report => `
                        <div class="report-card">
                            <div class="report-icon">📊</div>
                            <div class="report-info">
                                <div class="report-date">${report.date}</div>
                                <div class="report-time">${report.time}</div>
                            </div>
                            <a href="/reports/${report.filename}" class="view-btn">查看报告 →</a>
                        </div>
                    `).join('');
                }
            } catch (error) {
                console.error('加载报告失败:', error);
                reportsGrid.innerHTML = `
                    <div class="empty-state" style="grid-column: 1 / -1;">
                        <div class="icon">⚠️</div>
                        <h2>加载失败</h2>
                        <p>无法加载报告列表，请稍后重试</p>
                    </div>
                `;
            }
        }
        
        function filterReports() {
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const cards = document.querySelectorAll('.report-card');
            
            cards.forEach(card => {
                const date = card.querySelector('.report-date')?.textContent.toLowerCase() || '';
                const time = card.querySelector('.report-time')?.textContent.toLowerCase() || '';
                const text = date + ' ' + time;
                
                if (text.includes(searchTerm)) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        }
        
        // 页面加载时获取报告列表
        document.addEventListener('DOMContentLoaded', loadReports);
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
        
        <div id="reportsGrid" class="reports-grid">
            <div class="loading">⏳ 正在加载报告列表...</div>
        </div>
    </div>
</body>
</html>
"""
    return html

def upload_to_s3(bucket_name='resort-data-reports'):
    """上传主页到 S3"""
    s3_client = boto3.client('s3', region_name='us-west-2')
    
    html = generate_index_html()
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key='index.html',
            Body=html.encode('utf-8'),
            ContentType='text/html',
            CacheControl='max-age=300'
        )
        print(f"✅ 主页已上传到 s3://{bucket_name}/index.html")
        return True
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        return False

if __name__ == '__main__':
    print("🚀 生成并上传报告主页...")
    print("")
    
    success = upload_to_s3()
    
    if success:
        print("")
        print("✅ 完成！")
        print("")
        print("访问: https://monitoring.steponsnow.com")
        print("")
        print("注意: 首次 Lambda 采集完成后，报告列表才会有数据")
    else:
        print("")
        print("❌ 失败，请检查 AWS 凭证和权限")

