#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整流程：采集数据并保存到数据库
"""

import json
from collectors.openmeteo import OpenMeteoCollector
from normalizer import DataNormalizer
from db_manager import DatabaseManager

# 测试雪场配置
resort_config = {
    'id': 1,
    'name': 'Mammoth Mountain',
    'slug': 'mammoth-mountain',
    'location': 'California, USA',
    'lat': 37.6308,
    'lon': -119.0326,
    'elevation_min': 2424,
    'elevation_max': 3369,
    'data_source': 'openmeteo',
}

print("=" * 80)
print("🧪 完整流程测试：采集 → 标准化 → 保存")
print("=" * 80)
print(f"雪场: {resort_config['name']}")
print(f"海拔: {resort_config['elevation_min']}m - {resort_config['elevation_max']}m")
print()

# 1. 采集数据
print("📡 步骤 1: 采集天气数据")
print("-" * 80)
collector = OpenMeteoCollector(resort_config)
raw_data = collector.collect()

if not raw_data:
    print("❌ 采集失败")
    exit(1)

print("✅ 数据采集成功")
print()

# 2. 标准化
print("🔄 步骤 2: 标准化数据")
print("-" * 80)
weather_data = DataNormalizer.normalize(resort_config, raw_data, 'openmeteo')

if not weather_data:
    print("❌ 标准化失败")
    exit(1)

print("✅ 数据标准化成功")
print()
print("温度数据预览:")
print(f"  山脚: {weather_data.get('temp_base'):.1f}°C")
print(f"  山腰: {weather_data.get('temp_mid'):.1f}°C")
print(f"  山顶: {weather_data.get('temp_summit'):.1f}°C")
print(f"  冰冻线: {weather_data.get('freezing_level_current'):.0f}m")
print()

# 3. 保存到数据库
print("💾 步骤 3: 保存到数据库")
print("-" * 80)

# 构建完整的数据结构（模拟 collect_data.py 的逻辑）
normalized_data = {
    'resort_id': resort_config['id'],
    'name': resort_config['name'],
    'slug': resort_config['slug'],
    'location': resort_config['location'],
    'status': 'open',  # 假设状态
    'weather': weather_data
}

try:
    db_manager = DatabaseManager()
    success = db_manager.save_resort_data(resort_config, normalized_data)
    
    if success:
        print("✅ 数据保存成功")
        print()
        
        # 4. 验证数据
        print("🔍 步骤 4: 验证数据库")
        print("-" * 80)
        
        # 从数据库读取刚保存的数据
        from models import ResortWeather
        latest_weather = db_manager.session.query(ResortWeather).filter_by(
            resort_id=resort_config['id']
        ).order_by(ResortWeather.timestamp.desc()).first()
        
        if latest_weather:
            print("✅ 数据库验证成功")
            print()
            print("数据库中的温度数据:")
            print(f"  山脚: {latest_weather.temp_base}°C")
            print(f"  山腰: {latest_weather.temp_mid}°C")
            print(f"  山顶: {latest_weather.temp_summit}°C")
            print(f"  冰冻线: {latest_weather.freezing_level_current}m")
            print()
            
            # 检查 hourly_forecast
            hourly = latest_weather.hourly_forecast
            if hourly and len(hourly) > 0:
                print("24小时预报数据（第1小时）:")
                first_hour = hourly[0]
                print(f"  时间: {first_hour.get('time')}")
                print(f"  山脚: {first_hour.get('temp_base')}°C")
                print(f"  山腰: {first_hour.get('temp_mid')}°C")
                print(f"  山顶: {first_hour.get('temp_summit')}°C")
                print(f"  冰冻线: {first_hour.get('freezing_level')}m")
        else:
            print("❌ 未找到保存的数据")
    else:
        print("❌ 数据保存失败")
    
    db_manager.close()
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("✅ 测试完成！")
print("=" * 80)

