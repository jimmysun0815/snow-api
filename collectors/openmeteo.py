#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Meteo 天气数据采集器
提供天气预报、Freezing Level 等补充数据
"""

import requests
from typing import Optional, Dict, List
from .base import BaseCollector


class OpenMeteoCollector(BaseCollector):
    """Open-Meteo 天气采集器"""
    
    API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    def collect(self) -> Optional[Dict]:
        """
        从 Open-Meteo API 采集天气数据
        
        Returns:
            原始 JSON 数据或 None
        """
        # 从配置中获取经纬度
        lat = self.resort_config.get('lat')
        lon = self.resort_config.get('lon')
        
        if not lat or not lon:
            self.log('ERROR', '缺少经纬度信息')
            return None
        
        # API 参数
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': [
                'temperature_2m',
                'relativehumidity_2m',
                'windspeed_10m',
                'winddirection_10m',
                'freezinglevel_height',
                'weathercode',  # WMO天气代码
                # 气压层温度数据（用于按海拔计算温度）
                'temperature_1000hPa',  # ~110m
                'temperature_925hPa',   # ~750m
                'temperature_850hPa',   # ~1500m
                'temperature_700hPa',   # ~3000m
                'temperature_500hPa',   # ~5500m
            ],
            'daily': [
                'sunrise',
                'sunset',
                'temperature_2m_max',
                'temperature_2m_min',
                'precipitation_sum',
                'snowfall_sum',
                'windspeed_10m_max'
            ],
            'temperature_unit': 'celsius',
            'windspeed_unit': 'kmh',
            'precipitation_unit': 'mm',
            'timezone': 'auto',
            'forecast_days': 7
        }
        
        self.log('INFO', f'开始采集天气数据 (lat={lat}, lon={lon})')
        
        # 构建完整 URL（用于重试机制）
        import urllib.parse
        query_string = urllib.parse.urlencode(params, doseq=True)
        full_url = f"{self.API_BASE_URL}?{query_string}"
        
        # 使用带重试的请求方法
        response = self.fetch_with_retry(full_url, max_retries=3, timeout=10)
        
        if not response:
            return None
        
        try:
            data = response.json()
            self.log('INFO', '天气数据采集成功')
            return data
        except ValueError as e:
            self.log('ERROR', f'JSON 解析失败: {e}')
            return None
        except Exception as e:
            self.log('ERROR', f'未知错误: {str(e)}')
            return None
    
    @staticmethod
    def interpolate_temperature_at_elevation(
        target_elevation: float,
        pressure_temps: Dict[str, float]
    ) -> Optional[float]:
        """
        根据气压层温度数据插值计算指定海拔的温度
        
        Args:
            target_elevation: 目标海拔（米）
            pressure_temps: 气压层温度字典，例如:
                {
                    '1000hPa': 20.0,  # ~110m
                    '925hPa': 18.0,   # ~750m
                    '850hPa': 15.0,   # ~1500m
                    '700hPa': 8.0,    # ~3000m
                    '500hPa': -5.0,   # ~5500m
                }
        
        Returns:
            插值后的温度（摄氏度）或 None
        """
        # 气压层对应的大致海拔（米）
        pressure_elevations = {
            '1000hPa': 110,
            '925hPa': 750,
            '850hPa': 1500,
            '700hPa': 3000,
            '500hPa': 5500,
        }
        
        # 构建有效的海拔-温度对列表
        elevation_temp_pairs = []
        for pressure, elevation in pressure_elevations.items():
            if pressure in pressure_temps and pressure_temps[pressure] is not None:
                elevation_temp_pairs.append((elevation, pressure_temps[pressure]))
        
        if len(elevation_temp_pairs) < 2:
            return None
        
        # 按海拔排序
        elevation_temp_pairs.sort(key=lambda x: x[0])
        
        # 如果目标海拔低于最低点或高于最高点，使用外推
        elevations = [e for e, _ in elevation_temp_pairs]
        temps = [t for _, t in elevation_temp_pairs]
        
        if target_elevation <= elevations[0]:
            # 低于最低点，使用最低两点外推
            return temps[0] + (temps[1] - temps[0]) / (elevations[1] - elevations[0]) * (target_elevation - elevations[0])
        
        if target_elevation >= elevations[-1]:
            # 高于最高点，使用最高两点外推
            return temps[-1] + (temps[-1] - temps[-2]) / (elevations[-1] - elevations[-2]) * (target_elevation - elevations[-1])
        
        # 在范围内，找到目标海拔所在的区间并线性插值
        for i in range(len(elevations) - 1):
            if elevations[i] <= target_elevation <= elevations[i + 1]:
                # 线性插值
                ratio = (target_elevation - elevations[i]) / (elevations[i + 1] - elevations[i])
                return temps[i] + ratio * (temps[i + 1] - temps[i])
        
        return None

