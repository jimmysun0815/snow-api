#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Meteo 天气数据采集器
提供天气预报、Freezing Level 等补充数据
"""

import requests
from typing import Optional, Dict, List
from .base import BaseCollector
from config import Config


class OpenMeteoCollector(BaseCollector):
    """Open-Meteo 天气采集器"""
    
    # 根据是否有 API Key 选择不同的 API 端点
    API_BASE_URL_FREE = "https://api.open-meteo.com/v1/forecast"
    API_BASE_URL_PAID = "https://customer-api.open-meteo.com/v1/forecast"
    
    def collect(self) -> Optional[Dict]:
        """
        从 Open-Meteo API 采集天气数据
        
        优化策略：
        - Hourly 数据：采集 4 天（96小时，显示 72 小时足够）
        - Daily 数据：采集 8 天（确保完整的 7 天预报）
        
        Returns:
            原始 JSON 数据或 None
        """
        # 从配置中获取经纬度
        lat = self.resort_config.get('lat')
        lon = self.resort_config.get('lon')
        
        if not lat or not lon:
            self.log('ERROR', '缺少经纬度信息')
            return None
        
        # 确定 API 端点和 Key
        api_key = Config.OPENMETEO_API_KEY
        if api_key:
            api_url = self.API_BASE_URL_PAID
            self.log('INFO', f'开始采集天气数据 (lat={lat}, lon={lon}) [使用付费 API]')
        else:
            api_url = self.API_BASE_URL_FREE
            self.log('INFO', f'开始采集天气数据 (lat={lat}, lon={lon}) [使用免费 API]')
            # 免费 API 需要延迟以避免速率限制
            self.random_delay(1.0, 2.0)
        
        # 方案：发送一个请求，但 hourly 只采集 4 天，daily 采集 8 天
        # Open-Meteo API 支持 forecast_days 参数，但 hourly 和 daily 会使用相同的天数
        # 因此需要发送两个请求分别获取
        
        import urllib.parse
        
        # 请求 1：获取 4 天的 hourly 数据
        params_hourly = {
            'latitude': lat,
            'longitude': lon,
            'hourly': [
                'temperature_2m',
                'apparent_temperature',  # 体感温度
                'relativehumidity_2m',
                'windspeed_10m',
                'winddirection_10m',
                'freezinglevel_height',
                'weathercode',  # WMO天气代码
                'snowfall',  # 小时降雪量 (cm)
                'precipitation',  # 小时降水量 (mm)
                # 气压层温度数据（用于按海拔计算温度）
                'temperature_1000hPa',  # ~110m
                'temperature_925hPa',   # ~750m
                'temperature_850hPa',   # ~1500m
                'temperature_700hPa',   # ~3000m
                'temperature_500hPa',   # ~5500m
            ],
            'temperature_unit': 'celsius',
            'windspeed_unit': 'kmh',
            'precipitation_unit': 'mm',
            'timezone': 'auto',
            'forecast_days': 4  # 4天 hourly 数据（96小时）
        }
        
        if api_key:
            params_hourly['apikey'] = api_key
        
        query_hourly = urllib.parse.urlencode(params_hourly, doseq=True)
        url_hourly = f"{api_url}?{query_hourly}"
        
        response_hourly = self.fetch_with_retry(url_hourly, max_retries=3, timeout=30)
        if not response_hourly:
            return None
        
        try:
            data_hourly = response_hourly.json()
        except ValueError as e:
            self.log('ERROR', f'Hourly 数据 JSON 解析失败: {e}')
            return None
        
        # 请求 2：获取 8 天的 daily 数据
        params_daily = {
            'latitude': lat,
            'longitude': lon,
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
            'forecast_days': 8  # 8天 daily 数据
        }
        
        if api_key:
            params_daily['apikey'] = api_key
        
        query_daily = urllib.parse.urlencode(params_daily, doseq=True)
        url_daily = f"{api_url}?{query_daily}"
        
        response_daily = self.fetch_with_retry(url_daily, max_retries=3, timeout=30)
        if not response_daily:
            # 如果 daily 数据失败，仍然返回 hourly 数据
            self.log('WARNING', 'Daily 数据采集失败，仅返回 hourly 数据')
            return data_hourly
        
        try:
            data_daily = response_daily.json()
        except ValueError as e:
            self.log('ERROR', f'Daily 数据 JSON 解析失败: {e}')
            # 返回 hourly 数据
            return data_hourly
        
        # 合并两个响应
        # 将 daily 数据合并到 hourly 数据中
        if 'daily' in data_daily:
            data_hourly['daily'] = data_daily['daily']
            data_hourly['daily_units'] = data_daily.get('daily_units', {})
        
        self.log('INFO', '天气数据采集成功 (4天 hourly + 8天 daily)')
        return data_hourly
    
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

