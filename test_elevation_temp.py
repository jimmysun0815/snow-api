#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Open-Meteo API 的海拔温度数据
"""

import requests
import json

# 测试雪场：Mammoth Mountain
LAT = 37.6308
LON = -119.0326
ELEVATION_BASE = 2424  # 山脚
ELEVATION_SUMMIT = 3369  # 山顶

print("=" * 80)
print("🧪 测试 Open-Meteo API 海拔温度数据")
print("=" * 80)
print(f"雪场: Mammoth Mountain")
print(f"山脚: {ELEVATION_BASE}m")
print(f"山顶: {ELEVATION_SUMMIT}m")
print()

# 方法1: 使用气压层数据
print("📊 方法1: 气压层温度数据")
print("-" * 80)

params_pressure = {
    'latitude': LAT,
    'longitude': LON,
    'hourly': [
        'temperature_2m',  # 2米高度（地表）
        'temperature_1000hPa',  # ~110m
        'temperature_925hPa',   # ~750m
        'temperature_850hPa',   # ~1500m
        'temperature_700hPa',   # ~3000m
        'temperature_500hPa',   # ~5500m
    ],
    'temperature_unit': 'celsius',
    'timezone': 'auto',
    'forecast_hours': 1  # 只获取第一个小时
}

try:
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params=params_pressure,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        hourly = data.get('hourly', {})
        
        print(f"✅ API 调用成功！")
        print()
        print(f"当前时间: {hourly.get('time', [])[0]}")
        print()
        
        # 显示各层温度
        print("各气压层温度：")
        print(f"  地表 (2m):        {hourly.get('temperature_2m', [])[0]}°C")
        print(f"  1000 hPa (~110m): {hourly.get('temperature_1000hPa', [])[0]}°C")
        print(f"  925 hPa (~750m):  {hourly.get('temperature_925hPa', [])[0]}°C")
        print(f"  850 hPa (~1500m): {hourly.get('temperature_850hPa', [])[0]}°C")
        print(f"  700 hPa (~3000m): {hourly.get('temperature_700hPa', [])[0]}°C")
        print(f"  500 hPa (~5500m): {hourly.get('temperature_500hPa', [])[0]}°C")
        print()
        
        # 根据雪场海拔估算温度
        print("🏔️ 雪场海拔温度估算：")
        
        # 插值计算山脚温度（2424m）
        temp_850 = hourly.get('temperature_850hPa', [])[0]  # ~1500m
        temp_700 = hourly.get('temperature_700hPa', [])[0]  # ~3000m
        
        # 线性插值
        # 2424m 在 1500m 和 3000m 之间
        ratio = (2424 - 1500) / (3000 - 1500)
        temp_base = temp_850 + ratio * (temp_700 - temp_850)
        
        # 山顶温度（3369m）
        ratio_summit = (3369 - 3000) / (5500 - 3000)
        temp_summit = temp_700 + ratio_summit * (hourly.get('temperature_500hPa', [])[0] - temp_700)
        
        print(f"  山脚 ({ELEVATION_BASE}m): {temp_base:.1f}°C")
        print(f"  山顶 ({ELEVATION_SUMMIT}m): {temp_summit:.1f}°C")
        print(f"  温差: {abs(temp_base - temp_summit):.1f}°C")
        print()
        
    else:
        print(f"❌ API 调用失败: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ 错误: {e}")

print()
print("-" * 80)

# 方法2: 指定海拔（如果支持）
print("📊 方法2: 指定海拔参数")
print("-" * 80)

params_elevation = {
    'latitude': LAT,
    'longitude': LON,
    'elevation': ELEVATION_SUMMIT,  # 尝试指定海拔
    'hourly': 'temperature_2m',
    'temperature_unit': 'celsius',
    'timezone': 'auto',
    'forecast_hours': 1
}

try:
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params=params_elevation,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 支持 elevation 参数！")
        print(f"海拔 {ELEVATION_SUMMIT}m 的温度: {data['hourly']['temperature_2m'][0]}°C")
    else:
        print(f"⚠️  elevation 参数可能不支持或需要特殊端点")
        
except Exception as e:
    print(f"⚠️  {e}")

print()
print("=" * 80)
print("🎯 结论：")
print("  ✅ Open-Meteo 提供气压层温度数据")
print("  ✅ 可以通过插值计算任意海拔的温度")
print("  ✅ 适合滑雪场按海拔显示温度")
print("=" * 80)

