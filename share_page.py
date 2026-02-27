#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分享页面渲染服务
用于微信等社交平台分享时显示预览卡片

页面会：
1. 返回带有 Open Graph 标签的 HTML（微信爬虫抓取预览用）
2. 自动尝试打开 App（如果已安装）
3. 显示下载引导（如果未安装 App）
"""

import os
import requests
from datetime import datetime
from flask import Blueprint, Response
from dotenv import load_dotenv

load_dotenv()

# 创建 Blueprint
share_bp = Blueprint('share', __name__)

# Supabase 配置
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# App 下载链接
APP_STORE_URL = "https://apps.apple.com/app/id6740537880"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.steponsnow.snowapp"
LOGO_URL = "https://steponsnow.com/assets/logo-1024x1024.jpg"


def supabase_get(table: str, select: str = "*", filters: dict = None):
    """
    调用 Supabase REST API 查询数据
    
    Args:
        table: 表名
        select: 选择字段（支持关联查询）
        filters: 过滤条件，如 {"id": "eq.123"}
    
    Returns:
        查询结果列表
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise Exception("Supabase 配置缺失")
    
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {"select": select}
    
    if filters:
        params.update(filters)
    
    print(f"🌐 Supabase REST API: GET {url}")
    print(f"📋 查询参数: {params}")
    
    response = requests.get(url, headers=headers, params=params)
    
    print(f"📡 响应状态码: {response.status_code}")
    print(f"📊 响应内容: {response.text[:500]}")  # 只打印前500字符
    
    response.raise_for_status()
    return response.json()


def render_share_page(
    page_type: str,
    item_id: str,
    title: str,
    description: str,
    detail_lines: list,
    status_text: str = None,
    status_color: str = "#10B981"
) -> str:
    """
    渲染分享页面 HTML
    
    Args:
        page_type: 'carpool' 或 'accommodation'
        item_id: 帖子 ID
        title: 页面标题（用于 OG 标签）
        description: 页面描述（用于 OG 标签）
        detail_lines: 详情行列表，每行是 (icon, text) 元组
        status_text: 状态文本（如"招募中"）
        status_color: 状态颜色
    """
    
    # 构建 Deep Link
    app_scheme_url = f"steponsnow://{page_type}/{item_id}"
    page_url = f"https://steponsnow.com/share/{page_type}/{item_id}"
    
    # 构建详情 HTML
    detail_html = ""
    for icon, text in detail_lines:
        detail_html += f'''
            <div class="info-row">
                <span class="info-icon">{icon}</span>
                <span>{text}</span>
            </div>
        '''
    
    # 状态标签 HTML
    status_html = ""
    if status_text:
        status_html = f'''
            <div class="status-badge" style="background: {status_color}20; color: {status_color};">
                {status_text}
            </div>
        '''
    
    type_map = {"carpool": "拼车信息", "accommodation": "拼房信息", "news": "雪场新闻"}
    type_text = type_map.get(page_type, "详情")
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{title} - 逐风</title>
    <meta name="description" content="{description}">
    
    <!-- Open Graph / 微信分享 -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{page_url}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{LOGO_URL}">
    <meta property="og:site_name" content="逐风 Step On">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="summary">
    <meta property="twitter:url" content="{page_url}">
    <meta property="twitter:title" content="{title}">
    <meta property="twitter:description" content="{description}">
    <meta property="twitter:image" content="{LOGO_URL}">
    
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            color: white;
        }}
        
        .container {{
            max-width: 420px;
            width: 100%;
        }}
        
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        
        .logo {{
            width: 72px;
            height: 72px;
            border-radius: 16px;
            margin-bottom: 12px;
            box-shadow: 0 8px 32px rgba(139, 92, 246, 0.3);
        }}
        
        .app-name {{
            font-size: 22px;
            font-weight: 700;
            color: rgba(255,255,255,0.95);
            margin-bottom: 4px;
        }}
        
        .app-subtitle {{
            font-size: 13px;
            color: rgba(255,255,255,0.6);
            font-weight: 400;
        }}
        
        .card {{
            background: rgba(42, 49, 66, 0.95);
            border-radius: 20px;
            padding: 24px;
            margin: 16px 0;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .content-type {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: rgba(139, 92, 246, 0.2);
            color: #8B5CF6;
            border-radius: 20px;
            font-size: 13px;
            margin-bottom: 16px;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 8px;
        }}
        
        .content-title {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 20px;
            line-height: 1.4;
        }}
        
        .content-info {{
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 16px;
        }}
        
        .info-row {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 14px;
            color: rgba(255, 255, 255, 0.85);
            font-size: 15px;
            line-height: 1.5;
        }}
        
        .info-row:last-child {{ margin-bottom: 0; }}
        
        .info-icon {{
            font-size: 16px;
            flex-shrink: 0;
            width: 0px;
            text-align: center;
            display: none;
        }}
        
        .open-app-btn {{
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #8B5CF6, #6366F1);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            text-decoration: none;
            box-sizing: border-box;
        }}
        
        .open-app-btn:active {{
            transform: scale(0.98);
        }}
        
        .open-app-btn:visited {{
            color: white;
        }}
        
        .download-section {{
            margin-top: 24px;
            text-align: center;
        }}
        
        .download-title {{
            font-size: 14px;
            color: rgba(255,255,255,0.6);
            margin-bottom: 16px;
        }}
        
        .download-buttons {{
            display: flex;
            gap: 12px;
            justify-content: center;
        }}
        
        .download-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 20px;
            border-radius: 10px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
            flex: 1;
            max-width: 160px;
        }}
        
        .download-btn img {{
            width: 20px;
            height: 20px;
        }}
        
        .download-btn.ios {{
            background: rgba(255,255,255,0.1);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .download-btn.android {{
            background: rgba(16, 185, 129, 0.15);
            color: #10B981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        
        .footer {{
            margin-top: 32px;
            text-align: center;
            color: rgba(255, 255, 255, 0.4);
            font-size: 12px;
        }}
        
        .wechat-tip {{
            background: rgba(255, 159, 10, 0.1);
            border: 1px solid rgba(255, 159, 10, 0.3);
            border-radius: 12px;
            padding: 12px;
            margin-top: 16px;
            color: rgba(255, 159, 10, 0.9);
            font-size: 14px;
            text-align: center;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="{LOGO_URL}" alt="逐风" class="logo">
            <div class="app-name">逐风</div>
            <div class="app-subtitle">北美滑雪人的必备app</div>
        </div>
        
        <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                <div class="content-type">
                    <span>{type_text}</span>
                </div>
                {status_html}
            </div>
            
            <div class="content-info">
                {detail_html}
            </div>
            
            <a href="{app_scheme_url}" class="open-app-btn">
                <span>在 App 中查看详情</span>
            </a>
        </div>
        
        <div id="wechat-tip" class="wechat-tip" style="display: none;">
            点击右上角 <strong>···</strong> 按钮<br>
            选择 <strong>"在浏览器中打开"</strong><br>
            即可跳转到 App 查看详情
        </div>
        
        <div class="download-section">
            <div class="download-title">还没有安装？立即下载逐风 App</div>
            <div class="download-buttons">
                <a href="{APP_STORE_URL}" class="download-btn ios" id="ios-download">
                    <img src="https://developer.apple.com/assets/elements/icons/app-store/app-store-128x128.png" alt="App Store">
                    <span>App Store</span>
                </a>
                <a href="{PLAY_STORE_URL}" class="download-btn android" id="android-download">
                    <img src="https://www.gstatic.com/android/market_images/web/play_prism_hlock_2x.png" alt="Google Play" style="height: 20px; width: auto;">
                    <span>Google Play</span>
                </a>
            </div>
        </div>
        
        <div class="footer">
            © 2025 逐风 Step On. All rights reserved.
        </div>
    </div>
    
    <script>
        // 检测是否在微信中
        function isWeChat() {{
            const ua = navigator.userAgent.toLowerCase();
            return ua.indexOf('micromessenger') !== -1;
        }}
        
        // 如果在微信中，显示提示
        if (isWeChat()) {{
            document.addEventListener('DOMContentLoaded', function() {{
                // 隐藏打开App按钮
                const btn = document.querySelector('.open-app-btn');
                if (btn) {{
                    btn.style.display = 'none';
                }}
                
                // 显示微信提示
                const tip = document.getElementById('wechat-tip');
                if (tip) {{
                    tip.style.display = 'block';
                }}
            }});
        }}
    </script>
</body>
</html>'''
    
    return html


def render_not_found_page(page_type: str) -> str:
    """渲染 404 页面"""
    not_found_map = {"carpool": "拼车", "accommodation": "拼房", "news": "新闻"}
    type_text = not_found_map.get(page_type, "相关")
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信息不存在 - 逐风</title>
    <meta property="og:title" content="信息不存在 - 逐风">
    <meta property="og:description" content="该{type_text}信息已不存在或已被删除">
    <meta property="og:image" content="{LOGO_URL}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            text-align: center;
            padding: 20px;
        }}
        .container {{ max-width: 400px; }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ font-size: 24px; margin-bottom: 12px; }}
        p {{ color: rgba(255,255,255,0.6); margin-bottom: 24px; }}
        a {{
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #8B5CF6, #6366F1);
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">😢</div>
        <h1>信息不存在</h1>
        <p>该{type_text}信息已不存在或已被删除</p>
        <a href="https://steponsnow.com">返回首页</a>
    </div>
</body>
</html>'''


@share_bp.route('/share/carpool/<carpool_id>')
def share_carpool(carpool_id: str):
    """拼车分享页面"""
    try:
        print(f"🔍 查询拼车信息: {carpool_id}")
        print(f"🔑 SUPABASE_URL: {SUPABASE_URL}")
        print(f"🔑 SUPABASE_SERVICE_KEY 已配置: {bool(SUPABASE_SERVICE_KEY)}")
        
        # 通过 Supabase REST API 获取拼车信息（先不关联查询用户信息）
        carpools = supabase_get(
            table='carpool_posts',
            select='*',
            filters={'id': f'eq.{carpool_id}'}
        )
        
        print(f"📊 查询结果数量: {len(carpools) if carpools else 0}")
        
        if not carpools:
            print(f"❌ 未找到拼车信息: {carpool_id}")
            return Response(
                render_not_found_page('carpool'),
                status=404,
                mimetype='text/html; charset=utf-8'
            )
        
        carpool = carpools[0]
        
        # 获取雪场名称
        resort_name = "雪场"
        if carpool.get('resort_id'):
            resorts = supabase_get(
                table='resorts',
                select='name',
                filters={'id': f"eq.{carpool['resort_id']}"}
            )
            if resorts:
                resort_name = resorts[0].get('name', '雪场')
        
        # 解析数据
        departure_date = datetime.fromisoformat(carpool['departure_date'].replace('Z', '+00:00'))
        date_str = departure_date.strftime('%m月%d日')
        
        departure_time = carpool.get('departure_time', '')
        time_str = f" {departure_time}" if departure_time else ""
        
        # 状态
        status = carpool.get('status', 'open')
        status_map = {
            'open': ('招募中', '#10B981'),
            'full': ('已满员', '#6B7280'),
            'cancelled': ('已取消', '#EF4444'),
            'completed': ('已完成', '#6B7280')
        }
        status_text, status_color = status_map.get(status, ('', '#6B7280'))
        
        # 构建标题和描述
        title = f"拼车去{resort_name} - {date_str}"
        
        departure = carpool.get('departure_location', '')
        destination = carpool.get('destination_location') or resort_name
        seats = carpool.get('seats_available', 0)
        
        description = f"{departure} → {destination} | {date_str}{time_str} | 剩余{seats}个座位"
        
        # 价格
        price = carpool.get('price_per_seat')
        currency = carpool.get('currency', 'USD')
        currency_symbol = '$' if currency == 'USD' else 'C$'
        
        # 构建详情行（不使用emoji）
        detail_lines = [
            ('', f"路线: {departure} → {destination}"),
            ('', f"出发: {date_str}{time_str}"),
            ('', f"剩余 {seats} 个座位"),
        ]
        
        if price:
            detail_lines.append(('', f"价格: {currency_symbol}{int(price)}/座"))
        
        # 发布者（单独查询）
        try:
            user_id = carpool.get('user_id')
            if user_id:
                users = supabase_get(
                    table='user_profiles',
                    select='nickname',
                    filters={'user_id': f'eq.{user_id}'}
                )
                if users and users[0].get('nickname'):
                    detail_lines.append(('', f"发布者: {users[0]['nickname']}"))
        except Exception as e:
            print(f"⚠️ 获取用户信息失败: {e}")
        
        html = render_share_page(
            page_type='carpool',
            item_id=carpool_id,
            title=title,
            description=description,
            detail_lines=detail_lines,
            status_text=status_text,
            status_color=status_color
        )
        
        return Response(html, mimetype='text/html; charset=utf-8')
        
    except Exception as e:
        print(f"❌ 获取拼车信息失败: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            render_not_found_page('carpool'),
            status=500,
            mimetype='text/html; charset=utf-8'
        )


@share_bp.route('/share/accommodation/<accommodation_id>')
def share_accommodation(accommodation_id: str):
    """拼房分享页面"""
    try:
        print(f"🔍 查询拼房信息: {accommodation_id}")
        
        # 通过 Supabase REST API 获取拼房信息（先不关联查询用户信息）
        accommodations = supabase_get(
            table='accommodation_posts',
            select='*',
            filters={'id': f'eq.{accommodation_id}'}
        )
        
        print(f"📊 查询结果数量: {len(accommodations) if accommodations else 0}")
        
        if not accommodations:
            print(f"❌ 未找到拼房信息: {accommodation_id}")
            return Response(
                render_not_found_page('accommodation'),
                status=404,
                mimetype='text/html; charset=utf-8'
            )
        
        accommodation = accommodations[0]
        
        # 获取雪场名称
        resort_name = "雪场"
        if accommodation.get('resort_id'):
            resorts = supabase_get(
                table='resorts',
                select='name',
                filters={'id': f"eq.{accommodation['resort_id']}"}
            )
            if resorts:
                resort_name = resorts[0].get('name', '雪场')
        
        # 解析数据
        check_in_date = datetime.fromisoformat(accommodation['check_in_date'].replace('Z', '+00:00'))
        check_in_str = check_in_date.strftime('%m月%d日')
        
        check_out_date = accommodation.get('check_out_date')
        date_range = check_in_str
        if check_out_date:
            check_out = datetime.fromisoformat(check_out_date.replace('Z', '+00:00'))
            date_range = f"{check_in_str} - {check_out.strftime('%m月%d日')}"
        
        # 住宿类型
        acc_type = accommodation.get('accommodation_type', 'other')
        type_map = {
            'hotel': '酒店',
            'hostel': '青旅',
            'apartment': '公寓',
            'house': '民宿',
            'other': '住宿'
        }
        type_text = type_map.get(acc_type, '住宿')
        
        # 状态
        status = accommodation.get('status', 'open')
        status_map = {
            'open': ('招募中', '#10B981'),
            'full': ('已满员', '#6B7280'),
            'cancelled': ('已取消', '#EF4444'),
            'completed': ('已完成', '#6B7280')
        }
        status_text, status_color = status_map.get(status, ('', '#6B7280'))
        
        # 构建标题和描述
        title = f"拼房@{resort_name} - {check_in_str}"
        
        beds = accommodation.get('beds_available', 0)
        acc_name = accommodation.get('accommodation_name', '')
        
        description = f"{type_text}"
        if acc_name:
            description += f" {acc_name}"
        description += f" | {date_range} | 剩余{beds}床位"
        
        # 价格
        price = accommodation.get('price_per_bed')
        currency = accommodation.get('currency', 'USD')
        currency_symbol = '$' if currency == 'USD' else 'C$'
        
        # 构建详情行（不使用emoji）
        acc_info = f"{type_text}"
        if acc_name:
            acc_info += f" - {acc_name}"
        
        detail_lines = [
            ('', acc_info),
            ('', f"入住: {date_range}"),
            ('', f"剩余 {beds} 个床位"),
        ]
        
        if price:
            detail_lines.append(('', f"价格: {currency_symbol}{int(price)}/床位"))
        
        # 发布者（单独查询）
        try:
            user_id = accommodation.get('user_id')
            if user_id:
                users = supabase_get(
                    table='user_profiles',
                    select='nickname',
                    filters={'user_id': f'eq.{user_id}'}
                )
                if users and users[0].get('nickname'):
                    detail_lines.append(('', f"发布者: {users[0]['nickname']}"))
        except Exception as e:
            print(f"⚠️ 获取用户信息失败: {e}")
        
        html = render_share_page(
            page_type='accommodation',
            item_id=accommodation_id,
            title=title,
            description=description,
            detail_lines=detail_lines,
            status_text=status_text,
            status_color=status_color
        )
        
        return Response(html, mimetype='text/html; charset=utf-8')
        
    except Exception as e:
        print(f"❌ 获取拼房信息失败: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            render_not_found_page('accommodation'),
            status=500,
            mimetype='text/html; charset=utf-8'
        )


@share_bp.route('/share/news/<news_id>')
def share_news(news_id: str):
    """新闻分享页面"""
    try:
        news_list = supabase_get(
            table='resort_news',
            select='*',
            filters={'id': f'eq.{news_id}', 'is_enabled': 'eq.true'}
        )

        if not news_list:
            return Response(
                render_not_found_page('news'),
                status=404,
                mimetype='text/html; charset=utf-8'
            )

        news = news_list[0]

        resort_name = None
        resort_id = news.get('resort_id')
        if resort_id:
            try:
                resorts = supabase_get(
                    table='resorts',
                    select='name',
                    filters={'id': f'eq.{resort_id}'}
                )
                if resorts:
                    resort_name = resorts[0].get('name')
            except Exception:
                pass

        news_title = news.get('title', '')
        content = news.get('content', '')

        title = f"{resort_name} - {news_title}" if resort_name else news_title
        description = content[:150].replace('\n', ' ')

        detail_lines = [('', content[:300])]

        html = render_share_page(
            page_type='news',
            item_id=news_id,
            title=title,
            description=description,
            detail_lines=detail_lines,
        )

        return Response(html, mimetype='text/html; charset=utf-8')

    except Exception as e:
        print(f"获取新闻信息失败: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            render_not_found_page('news'),
            status=500,
            mimetype='text/html; charset=utf-8'
        )
