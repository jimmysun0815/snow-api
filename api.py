#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REST API 服务
提供雪场数据查询接口
从 PostgreSQL + Redis 读取数据
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from db_manager import DatabaseManager
from datetime import datetime
import math

app = Flask(__name__)
CORS(app)  # 启用 CORS，允许跨域请求

# 初始化数据库管理器
try:
    db_manager = DatabaseManager()
    print("✅ API 使用数据库模式（PostgreSQL + Redis 缓存）")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    db_manager = None


@app.route('/api/resorts', methods=['GET'])
def get_all_resorts():
    """获取所有雪场数据"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    resorts = db_manager.get_all_resorts_data()
    
    if not resorts:
        return jsonify({
            'error': '暂无数据',
            'message': '请先运行数据采集'
        }), 404
    
    return jsonify({
        'resorts': resorts,
        'metadata': {
            'total_resorts': len(resorts),
            'timestamp': datetime.now().isoformat()
        }
    })


@app.route('/api/resorts/<int:resort_id>', methods=['GET'])
def get_resort_by_id(resort_id):
    """根据 ID 获取单个雪场数据"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    resort = db_manager.get_latest_resort_data(resort_id=resort_id)
    
    if not resort:
        return jsonify({
            'error': '未找到雪场',
            'resort_id': resort_id
        }), 404
    
    return jsonify(resort)


@app.route('/api/resorts/slug/<slug>', methods=['GET'])
def get_resort_by_slug(slug):
    """根据 slug 获取单个雪场数据"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    resort = db_manager.get_latest_resort_data(resort_slug=slug)
    
    if not resort:
        return jsonify({
            'error': '未找到雪场',
            'slug': slug
        }), 404
    
    return jsonify(resort)


@app.route('/api/resorts/open', methods=['GET'])
def get_open_resorts():
    """获取所有开放的雪场"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    all_resorts = db_manager.get_all_resorts_data()
    open_resorts = [r for r in all_resorts if r.get('status') in ['open', 'partial']]
    
    return jsonify({
        'resorts': open_resorts,
        'metadata': {
            'total_open': len(open_resorts),
            'timestamp': datetime.now().isoformat()
        }
    })


@app.route('/api/resorts/search', methods=['GET'])
def search_resorts():
    """搜索雪场"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    name_query = request.args.get('name', '').lower()
    location_query = request.args.get('location', '').lower()
    
    all_resorts = db_manager.get_all_resorts_data()
    filtered = []
    
    for resort in all_resorts:
        match_name = name_query and name_query in resort.get('name', '').lower()
        match_location = location_query and location_query in resort.get('location', '').lower()
        
        if match_name or match_location:
            filtered.append(resort)
    
    return jsonify({
        'resorts': filtered,
        'metadata': {
            'total_found': len(filtered),
            'query': {
                'name': name_query,
                'location': location_query
            }
        }
    })


@app.route('/api/resorts/nearby', methods=['GET'])
def get_nearby_resorts():
    """查询附近的雪场"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius', 50))  # 默认50km
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid parameters'}), 400
    
    all_resorts = db_manager.get_all_resorts_data()
    nearby = []
    
    for resort in all_resorts:
        resort_lat = resort.get('lat')
        resort_lon = resort.get('lon')
        
        if resort_lat and resort_lon:
            # 简单的距离计算（Haversine公式）
            distance = calculate_distance(lat, lon, resort_lat, resort_lon)
            if distance <= radius:
                resort['distance'] = round(distance, 2)
                nearby.append(resort)
    
    # 按距离排序
    nearby.sort(key=lambda x: x.get('distance', 0))
    
    return jsonify({
        'resorts': nearby,
        'metadata': {
            'total_found': len(nearby),
            'center': {'lat': lat, 'lon': lon},
            'radius_km': radius
        }
    })


@app.route('/api/resorts/<int:resort_id>/trails', methods=['GET'])
def get_resort_trails_by_id(resort_id):
    """获取雪场的雪道数据（按ID）
    
    Query Parameters:
        type: 过滤雪道类型 (downhill, nordic, sled, hike, snow_park 等)
        difficulty: 过滤难度 (easy, intermediate, advanced, expert 等)
    """
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    trails = db_manager.get_resort_trails(resort_id=resort_id)
    
    if not trails:
        return jsonify({
            'error': '未找到雪道数据',
            'resort_id': resort_id,
            'message': '该雪场可能还未采集雪道数据'
        }), 404
    
    # 获取过滤参数
    filter_type = request.args.get('type')
    filter_difficulty = request.args.get('difficulty')
    
    # 应用过滤
    filtered_trails = trails
    if filter_type:
        filtered_trails = [t for t in filtered_trails if t.get('piste_type') == filter_type]
    if filter_difficulty:
        filtered_trails = [t for t in filtered_trails if t.get('difficulty') == filter_difficulty]
    
    # 统计信息
    difficulty_stats = {}
    type_stats = {}
    total_length = 0
    
    for trail in filtered_trails:
        diff = trail.get('difficulty', 'unknown')
        ptype = trail.get('piste_type', 'unknown')
        difficulty_stats[diff] = difficulty_stats.get(diff, 0) + 1
        type_stats[ptype] = type_stats.get(ptype, 0) + 1
        total_length += trail.get('length_meters', 0)
    
    return jsonify({
        'resort_id': resort_id,
        'total_trails': len(filtered_trails),
        'total_length_km': round(total_length / 1000, 2),
        'difficulty_stats': difficulty_stats,
        'type_stats': type_stats,
        'filters_applied': {
            'type': filter_type,
            'difficulty': filter_difficulty
        },
        'trails': filtered_trails
    })


@app.route('/api/resorts/slug/<slug>/trails', methods=['GET'])
def get_resort_trails_by_slug(slug):
    """获取雪场的雪道数据（按slug）
    
    Query Parameters:
        type: 过滤雪道类型 (downhill, nordic, sled, hike, snow_park 等)
        difficulty: 过滤难度 (easy, intermediate, advanced, expert 等)
    """
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    trails = db_manager.get_resort_trails(resort_slug=slug)
    
    if not trails:
        return jsonify({
            'error': '未找到雪道数据',
            'slug': slug,
            'message': '该雪场可能还未采集雪道数据'
        }), 404
    
    # 获取过滤参数
    filter_type = request.args.get('type')
    filter_difficulty = request.args.get('difficulty')
    
    # 应用过滤
    filtered_trails = trails
    if filter_type:
        filtered_trails = [t for t in filtered_trails if t.get('piste_type') == filter_type]
    if filter_difficulty:
        filtered_trails = [t for t in filtered_trails if t.get('difficulty') == filter_difficulty]
    
    # 统计信息
    difficulty_stats = {}
    type_stats = {}
    total_length = 0
    
    for trail in filtered_trails:
        diff = trail.get('difficulty', 'unknown')
        ptype = trail.get('piste_type', 'unknown')
        difficulty_stats[diff] = difficulty_stats.get(diff, 0) + 1
        type_stats[ptype] = type_stats.get(ptype, 0) + 1
        total_length += trail.get('length_meters', 0)
    
    return jsonify({
        'slug': slug,
        'total_trails': len(filtered_trails),
        'total_length_km': round(total_length / 1000, 2),
        'difficulty_stats': difficulty_stats,
        'type_stats': type_stats,
        'filters_applied': {
            'type': filter_type,
            'difficulty': filter_difficulty
        },
        'trails': filtered_trails
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    status = {
        'status': 'running',
        'message': 'API is operational',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if db_manager else 'disconnected'
    }
    
    if db_manager:
        try:
            # 测试数据库连接
            resorts = db_manager.get_all_resorts_data()
            status['total_resorts'] = len(resorts)
        except:
            status['database'] = 'error'
    
    return jsonify(status)


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    计算两点之间的距离（Haversine公式）
    
    Returns:
        距离（公里）
    """
    R = 6371  # 地球半径（公里）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🚀 Flask API 服务已启动")
    print("=" * 80)
    print("  API 地址: http://localhost:8000")
    print("  数据源: PostgreSQL + Redis 缓存")
    print()
    print("  雪场数据:")
    print("    GET /api/resorts                      - 获取所有雪场")
    print("    GET /api/resorts/<id>                 - 获取特定雪场（按ID）")
    print("    GET /api/resorts/slug/<slug>          - 获取特定雪场（按slug）")
    print("    GET /api/resorts/open                 - 获取开放的雪场")
    print("    GET /api/resorts/search               - 搜索雪场")
    print("    GET /api/resorts/nearby               - 查询附近雪场")
    print()
    print("  雪道数据:")
    print("    GET /api/resorts/<id>/trails          - 获取雪场雪道（按ID）")
    print("    GET /api/resorts/slug/<slug>/trails   - 获取雪场雪道（按slug）")
    print()
    print("  系统:")
    print("    GET /api/status                       - 获取系统状态")
    print()
    print("=" * 80)
    print()
    
    app.run(host='0.0.0.0', port=8000, debug=True)
