#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Meteo 天气数据采集器
提供天气预报、Freezing Level 等补充数据
"""

import requests
from typing import Optional, Dict
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
                'freezinglevel_height'
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

