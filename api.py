#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REST API Service - Provides resort data query endpoints
# Reads from PostgreSQL + Redis

from flask import Flask, jsonify, request
from flask_cors import CORS
from db_manager import DatabaseManager
from share_page import share_bp
from datetime import datetime
import math
import json
import os

app = Flask(__name__)
CORS(app)  # 启用 CORS，允许跨域请求

# 注册分享页面 Blueprint
app.register_blueprint(share_bp)

# 初始化数据库管理器
try:
    db_manager = DatabaseManager()
    print("[OK] API 使用数据库模式（PostgreSQL + Redis 缓存）")
except Exception as e:
    print(f"[ERROR] 数据库连接失败: {e}")
    db_manager = None

# 加载雪场配置（包含海拔等静态信息）
_resort_config_cache = None

def load_resort_config():
    """加载雪场配置文件（缓存）"""
    global _resort_config_cache
    if _resort_config_cache is not None:
        return _resort_config_cache
    
    config_path = os.path.join(os.path.dirname(__file__), 'resorts_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            # 转换为字典，以 ID 为 key
            _resort_config_cache = {
                resort['id']: resort 
                for resort in config_data.get('resorts', [])
            }
            print(f"[OK] 已加载 {len(_resort_config_cache)} 个雪场配置")
            return _resort_config_cache
    except Exception as e:
        print(f"[ERROR] 加载配置文件失败: {e}")
        return {}

def merge_resort_config(resort_data):
    """将配置文件中的静态数据合并到雪场数据中"""
    config = load_resort_config()
    resort_id = resort_data.get('id')
    
    if resort_id and resort_id in config:
        resort_config = config[resort_id]
        # 合并海拔数据（优先使用配置文件）
        if 'elevation_min' in resort_config:
            resort_data['elevation_min'] = resort_config['elevation_min']
        if 'elevation_max' in resort_config:
            resort_data['elevation_max'] = resort_config['elevation_max']
    
    return resort_data


@app.route('/api/resorts', methods=['GET'])
def get_all_resorts():
    """获取所有雪场数据（完整版，包含天气预报）"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    resorts = db_manager.get_all_resorts_data()
    
    if not resorts:
        return jsonify({
            'error': '暂无数据',
            'message': '请先运行数据采集'
        }), 404
    
    # 合并配置数据（海拔等静态信息）
    resorts = [merge_resort_config(r) for r in resorts]
    
    return jsonify({
        'resorts': resorts,
        'metadata': {
            'total_resorts': len(resorts),
            'timestamp': datetime.now().isoformat()
        }
    })


@app.route('/api/resorts/summary', methods=['GET'])
def get_resorts_summary():
    """获取所有雪场摘要（轻量级，不含完整天气预报）"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    summaries = db_manager.get_all_resorts_summary()
    
    if not summaries:
        return jsonify({
            'error': '暂无数据',
            'message': '请先运行数据采集'
        }), 404
    
    # 合并配置数据（海拔等静态信息）
    summaries = [merge_resort_config(s) for s in summaries]
    
    return jsonify({
        'resorts': summaries,
        'metadata': {
            'total_resorts': len(summaries),
            'data_type': 'summary',
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
    
    # 合并配置数据
    resort = merge_resort_config(resort)
    
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
    
    # 合并配置数据
    resort = merge_resort_config(resort)
    
    return jsonify(resort)


@app.route('/api/resorts/open', methods=['GET'])
def get_open_resorts():
    """获取所有开放的雪场"""
    if not db_manager:
        return jsonify({'error': '数据库未连接'}), 500
    
    all_resorts = db_manager.get_all_resorts_data()
    open_resorts = [r for r in all_resorts if r.get('status') in ['open', 'partial']]
    
    # 合并配置数据
    open_resorts = [merge_resort_config(r) for r in open_resorts]
    
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


# ==================== Admin API ====================

def verify_admin_api_key():
    """验证 Admin API Key"""
    api_key = request.headers.get('X-Admin-API-Key')
    expected_key = os.getenv('ADMIN_API_KEY')
    
    if not expected_key:
        return False, "Admin API Key 未配置"
    
    if not api_key:
        return False, "缺少 X-Admin-API-Key header"
    
    if api_key != expected_key:
        return False, "API Key 无效"
    
    return True, None


@app.route('/api/admin/resorts/<int:resort_id>', methods=['DELETE'])
def admin_delete_resort(resort_id):
    """
    禁用雪场（软删除，设置 enabled=false）
    
    ⚠️ 需要 Admin API Key 认证
    ✅ 这是软删除，数据仍保留在 RDS，可以恢复
    
    Headers:
        X-Admin-API-Key: 管理员 API Key
    
    Returns:
        200: 禁用成功
        401: 未授权
        404: 雪场不存在
        500: 服务器错误
    """
    # 验证 API Key
    is_valid, error_msg = verify_admin_api_key()
    if not is_valid:
        return jsonify({
            'success': False,
            'error': error_msg
        }), 401
    
    if not db_manager:
        return jsonify({
            'success': False,
            'error': '数据库未连接'
        }), 500
    
    try:
        # 调用禁用方法（软删除）
        result = db_manager.disable_resort(resort_id)
        
        print(f"✅ [Admin API] 禁用雪场 (软删除): ID={result['resort_id']}, Name={result['resort_name']}")
        
        return jsonify({
            'success': True,
            'message': f'成功禁用雪场: {result["resort_name"]}',
            'resort_id': result['resort_id'],
            'resort_name': result['resort_name'],
            'action': 'disabled'  # 标记这是禁用操作
        }), 200
    
    except ValueError as e:
        # 雪场不存在
        print(f"⚠️  [Admin API] 雪场不存在: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    
    except Exception as e:
        print(f"❌ [Admin API] 禁用雪场失败: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'禁用失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("[START] Flask API 服务已启动")
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
    print("  分享页面（微信/社交分享）:")
    print("    GET /share/carpool/<id>               - 拼车分享页面")
    print("    GET /share/accommodation/<id>         - 拼房分享页面")
    print()
    print("  系统:")
    print("    GET /api/status                       - 获取系统状态")
    print()
    print("=" * 80)
    print()
    
    app.run(host='0.0.0.0', port=8000, debug=True)
