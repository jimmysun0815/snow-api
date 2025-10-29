#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据标准化器
将不同数据源的数据转换为统一的标准格式
"""

from typing import Dict, Optional
from datetime import datetime


class DataNormalizer:
    """数据标准化器"""
    
    @staticmethod
    def normalize(resort_config: Dict, raw_data: Dict, data_source: str) -> Optional[Dict]:
        """
        标准化数据
        
        Args:
            resort_config: 雪场配置
            raw_data: 原始数据
            data_source: 数据源类型 (mtnpowder, onthesnow, openmeteo)
            
        Returns:
            标准化后的数据字典
        """
        if data_source == 'mtnpowder':
            return DataNormalizer._normalize_mtnpowder(resort_config, raw_data)
        elif data_source == 'onthesnow':
            return DataNormalizer._normalize_onthesnow(resort_config, raw_data)
        elif data_source == 'openmeteo':
            return DataNormalizer._normalize_openmeteo(resort_config, raw_data)
        else:
            return None
    
    @staticmethod
    def _normalize_mtnpowder(resort_config: Dict, raw_data: Dict) -> Dict:
        """标准化 MtnPowder 数据"""
        
        snow_report = raw_data.get('SnowReport', {})
        current_conditions = raw_data.get('CurrentConditions', {})
        base_station = current_conditions.get('Base', {})
        
        # 状态判断
        operating_status = raw_data.get('OperatingStatus', '')
        if 'Open' in operating_status and snow_report.get('TotalOpenLifts', 0) > 0:
            status = 'open'
        elif 'Open' in operating_status:
            status = 'partial'
        else:
            status = 'closed'
        
        return {
            'resort_id': resort_config.get('id'),
            'name': resort_config.get('name'),
            'slug': resort_config.get('slug'),
            'location': resort_config.get('location'),
            'lat': resort_config.get('lat'),
            'lon': resort_config.get('lon'),
            'status': status,
            'new_snow': snow_report.get('StormTotalCM', 0),
            'base_depth': 0,  # MtnPowder 没有直接提供，需要解析
            'lifts_open': snow_report.get('TotalOpenLifts', 0),
            'lifts_total': snow_report.get('TotalLifts', 0),
            'trails_open': snow_report.get('TotalOpenTrails', 0),
            'trails_total': snow_report.get('TotalTrails', 0),
            'temperature': float(base_station.get('TemperatureC', 0)) if base_station.get('TemperatureC') else 0,
            'last_update': datetime.now().isoformat(),
            'source': f"https://www.mtnpowder.com/feed?resortId={resort_config.get('source_id')}",
            'data_source': 'mtnpowder'
        }
    
    @staticmethod
    def _normalize_onthesnow(resort_config: Dict, raw_data: Dict) -> Dict:
        """标准化 OnTheSnow 数据"""
        
        props = raw_data.get('props', {}).get('pageProps', {})
        full_resort = props.get('fullResort', {})
        short_weather = props.get('shortWeather', {})
        
        # 雪况数据
        snow = full_resort.get('snow', {})
        lifts = full_resort.get('lifts', {})
        runs = full_resort.get('runs', {})
        status_info = full_resort.get('status', {})
        
        # 状态判断
        open_flag = status_info.get('openFlag', 2)
        if open_flag == 0:
            status = 'open'
        elif open_flag == 1:
            status = 'partial'
        else:
            status = 'closed'
        
        # 基础积雪（优先使用 base，如果没有则用 summit）
        base_depth = snow.get('base') or snow.get('summit') or 0
        if base_depth is None:
            base_depth = 0
        
        # 温度（使用平均温度）
        weather_temp = short_weather.get('temp', {})
        temp_min = weather_temp.get('min', 0)
        temp_max = weather_temp.get('max', 0)
        avg_temp = (temp_min + temp_max) / 2 if temp_min and temp_max else 0
        
        return {
            'resort_id': resort_config.get('id'),
            'name': full_resort.get('title') or resort_config.get('name'),
            'slug': resort_config.get('slug'),
            'location': resort_config.get('location'),
            'lat': full_resort.get('latitude') or resort_config.get('lat'),
            'lon': full_resort.get('longitude') or resort_config.get('lon'),
            'status': status,
            'new_snow': snow.get('last24', 0) or 0,
            'base_depth': base_depth,
            'lifts_open': lifts.get('open', 0),
            'lifts_total': lifts.get('total', 0),
            'trails_open': runs.get('open', 0),
            'trails_total': runs.get('total', 0),
            'temperature': round(avg_temp, 1),
            'last_update': datetime.now().isoformat(),
            'source': resort_config.get('source_url'),
            'data_source': 'onthesnow',
            # 额外信息
            'opening_date': status_info.get('openingDate'),
            'closing_date': status_info.get('closingDate'),
        }
    
    @staticmethod
    def _normalize_openmeteo(resort_config: Dict, raw_data: Dict) -> Dict:
        """标准化 Open-Meteo 天气数据"""
        
        hourly = raw_data.get('hourly', {})
        daily = raw_data.get('daily', {})
        
        # 当前天气数据（取第一个小时的值）
        temperatures = hourly.get('temperature_2m', [])
        humidities = hourly.get('relativehumidity_2m', [])
        windspeeds = hourly.get('windspeed_10m', [])
        winddirections = hourly.get('winddirection_10m', [])
        freezing_levels = hourly.get('freezinglevel_height', [])
        
        current_temp = temperatures[0] if temperatures else None
        current_humidity = humidities[0] if humidities else None
        current_windspeed = windspeeds[0] if windspeeds else None
        current_winddirection = winddirections[0] if winddirections else None
        current_freezing_level = freezing_levels[0] if freezing_levels else None
        
        # 未来24小时平均冰冻高度
        avg_freezing_level_24h = None
        if freezing_levels and len(freezing_levels) >= 24:
            avg_freezing_level_24h = round(sum(freezing_levels[:24]) / 24, 1)
        
        # 未来24小时平均风速
        avg_windspeed_24h = None
        if windspeeds and len(windspeeds) >= 24:
            avg_windspeed_24h = round(sum(windspeeds[:24]) / 24, 1)
        
        # 未来24小时的详细数据
        hourly_forecast = []
        times = hourly.get('time', [])
        for i in range(min(24, len(times))):
            hourly_forecast.append({
                'time': times[i] if i < len(times) else None,
                'temperature': temperatures[i] if i < len(temperatures) else None,
                'humidity': humidities[i] if i < len(humidities) else None,
                'windspeed': windspeeds[i] if i < len(windspeeds) else None,
                'winddirection': winddirections[i] if i < len(winddirections) else None,
                'freezing_level': freezing_levels[i] if i < len(freezing_levels) else None,
            })
        
        # 今天的天气数据
        today_data = {}
        if daily:
            times = daily.get('time', [])
            sunrises = daily.get('sunrise', [])
            sunsets = daily.get('sunset', [])
            if times:
                today_data = {
                    'date': times[0],
                    'sunrise': sunrises[0] if sunrises else None,
                    'sunset': sunsets[0] if sunsets else None,
                    'temp_max': daily.get('temperature_2m_max', [None])[0],
                    'temp_min': daily.get('temperature_2m_min', [None])[0],
                    'precipitation': daily.get('precipitation_sum', [None])[0],
                    'snowfall': daily.get('snowfall_sum', [None])[0],
                    'windspeed_max': daily.get('windspeed_10m_max', [None])[0],
                }
        
        # 未来7天预报
        forecast_7d = []
        if daily:
            times = daily.get('time', [])
            temps_max = daily.get('temperature_2m_max', [])
            temps_min = daily.get('temperature_2m_min', [])
            snowfall = daily.get('snowfall_sum', [])
            precipitation = daily.get('precipitation_sum', [])
            
            for i in range(min(7, len(times))):
                forecast_7d.append({
                    'date': times[i] if i < len(times) else None,
                    'temp_max': temps_max[i] if i < len(temps_max) else None,
                    'temp_min': temps_min[i] if i < len(temps_min) else None,
                    'snowfall': snowfall[i] if i < len(snowfall) else None,
                    'precipitation': precipitation[i] if i < len(precipitation) else None,
                })
        
        # 风向转换为方位
        def wind_direction_to_compass(degrees):
            if degrees is None:
                return None
            directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            idx = round(degrees / 45) % 8
            return directions[idx]
        
        return {
            'resort_id': resort_config.get('id'),
            # 当前天气
            'current': {
                'temperature': current_temp,
                'humidity': current_humidity,
                'windspeed': current_windspeed,
                'winddirection': current_winddirection,
                'winddirection_compass': wind_direction_to_compass(current_winddirection),
            },
            # 冰冻线
            'freezing_level_current': current_freezing_level,
            'freezing_level_24h_avg': avg_freezing_level_24h,
            # 今日数据
            'today': today_data,
            # 24小时预报
            'hourly_forecast': hourly_forecast,
            # 7天预报
            'forecast_7d': forecast_7d,
            # 统计
            'avg_windspeed_24h': avg_windspeed_24h,
            # 元数据
            'last_update': datetime.now().isoformat(),
            'source': 'Open-Meteo API',
            'data_source': 'openmeteo'
        }

