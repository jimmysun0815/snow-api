#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据标准化器
将不同数据源的数据转换为统一的标准格式
"""

from typing import Dict, Optional
from datetime import datetime
from collectors.openmeteo import OpenMeteoCollector


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
        
        # 处理温度（可能是 '--' 字符串）
        def safe_float(value, default=0):
            """安全转换为 float，处理 None 和 '--' 等无效值"""
            if value is None:
                return default
            if isinstance(value, str) and (value.strip() == '--' or value.strip() == ''):
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        temp_c = base_station.get('TemperatureC')
        temperature = safe_float(temp_c, 0)
        
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
            'temperature': temperature,
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
        base_depth = snow.get('base') or snow.get('summit')
        
        # 山顶积雪
        summit_depth = snow.get('summit')
        
        # 温度（使用平均温度）
        weather_temp = short_weather.get('temp', {})
        temp_min = weather_temp.get('min', 0)
        temp_max = weather_temp.get('max', 0)
        avg_temp = (temp_min + temp_max) / 2 if temp_min and temp_max else 0
        
        # 辅助函数：处理 None 值和无效字符串
        def handle_none_as_zero(value):
            """如果是 None 或无效字符串（如'--'）返回 0，否则返回数值"""
            if value is None:
                return 0
            if isinstance(value, str) and (value.strip() == '--' or value.strip() == ''):
                return 0
            try:
                return float(value) if value else 0
            except (ValueError, TypeError):
                return 0
        
        def handle_none_preserve(value):
            """如果是 None 或无效字符串（如'--'）保留 None，否则返回数值（用于积雪深度等可选数据）"""
            if value is None:
                return None
            if isinstance(value, str) and (value.strip() == '--' or value.strip() == ''):
                return None
            try:
                return float(value) if value else None
            except (ValueError, TypeError):
                return None
        
        return {
            'resort_id': resort_config.get('id'),
            'name': full_resort.get('title') or resort_config.get('name'),
            'slug': resort_config.get('slug'),
            'location': resort_config.get('location'),
            'lat': full_resort.get('latitude') or resort_config.get('lat'),
            'lon': full_resort.get('longitude') or resort_config.get('lon'),
            'status': status,
            'new_snow': snow.get('last24') or 0,
            'base_depth': handle_none_preserve(base_depth),
            'snow_base': handle_none_preserve(base_depth),  # 兼容字段
            'snow_summit': handle_none_preserve(summit_depth),  # 兼容字段
            'lifts_open': handle_none_as_zero(lifts.get('open')),
            'lifts_total': handle_none_as_zero(lifts.get('total')),
            'trails_open': handle_none_as_zero(runs.get('open')),
            'trails_total': handle_none_as_zero(runs.get('total')),
            'temperature': round(avg_temp, 1) if avg_temp else None,
            'last_update': datetime.now().isoformat(),
            'source': resort_config.get('source_url'),
            'data_source': 'onthesnow',
            # 额外信息
            'opening_date': status_info.get('openingDate'),
            'closing_date': status_info.get('closingDate'),
            # Webcam 数据
            'webcams': DataNormalizer._extract_webcams(full_resort),
        }
    
    @staticmethod
    def _extract_webcams(full_resort: Dict) -> list:
        """
        从 OnTheSnow 数据中提取 webcam 信息
        
        Args:
            full_resort: OnTheSnow 的 fullResort 对象
            
        Returns:
            webcam 数据列表
        """
        webcams = full_resort.get('webcams', [])
        if not webcams:
            return []
        
        result = []
        for cam in webcams:
            webcam_data = {
                'webcam_uuid': cam.get('uuid'),
                'title': cam.get('title'),
                'image_url': cam.get('image'),
                'thumbnail_url': cam.get('thumbnail'),
                'video_stream_url': cam.get('videoStream'),
                'webcam_type': cam.get('webcamType', 0),
                'is_featured': cam.get('isFeatured', False),
                'last_updated': cam.get('date'),  # ISO 格式的时间字符串
            }
            result.append(webcam_data)
        
        return result
    
    @staticmethod
    def _normalize_openmeteo(resort_config: Dict, raw_data: Dict) -> Dict:
        """标准化 Open-Meteo 天气数据"""
        
        hourly = raw_data.get('hourly', {})
        daily = raw_data.get('daily', {})
        
        # 当前天气数据（取第一个小时的值）
        temperatures = hourly.get('temperature_2m', [])
        apparent_temperatures = hourly.get('apparent_temperature', [])  # 体感温度
        humidities = hourly.get('relativehumidity_2m', [])
        windspeeds = hourly.get('windspeed_10m', [])
        winddirections = hourly.get('winddirection_10m', [])
        freezing_levels = hourly.get('freezinglevel_height', [])
        weathercodes = hourly.get('weathercode', [])
        snowfalls = hourly.get('snowfall', [])  # 小时降雪量 (cm)
        precipitations = hourly.get('precipitation', [])  # 小时降水量 (mm)
        
        current_temp = temperatures[0] if temperatures else None
        current_apparent_temp = apparent_temperatures[0] if apparent_temperatures else None
        current_humidity = humidities[0] if humidities else None
        current_windspeed = windspeeds[0] if windspeeds else None
        current_winddirection = winddirections[0] if winddirections else None
        current_freezing_level = freezing_levels[0] if freezing_levels else None
        
        # 气压层温度数据
        temp_1000hPa = hourly.get('temperature_1000hPa', [])
        temp_925hPa = hourly.get('temperature_925hPa', [])
        temp_850hPa = hourly.get('temperature_850hPa', [])
        temp_700hPa = hourly.get('temperature_700hPa', [])
        temp_500hPa = hourly.get('temperature_500hPa', [])
        
        # 计算当前山脚、山腰、山顶的温度
        elevation_min = resort_config.get('elevation_min')
        elevation_max = resort_config.get('elevation_max')
        current_temp_base = None
        current_temp_mid = None
        current_temp_summit = None
        
        if elevation_min and elevation_max:
            # 当前时刻的气压层温度
            current_pressure_temps = {
                '1000hPa': temp_1000hPa[0] if temp_1000hPa else None,
                '925hPa': temp_925hPa[0] if temp_925hPa else None,
                '850hPa': temp_850hPa[0] if temp_850hPa else None,
                '700hPa': temp_700hPa[0] if temp_700hPa else None,
                '500hPa': temp_500hPa[0] if temp_500hPa else None,
            }
            
            # 插值计算，添加合理性检查
            temp_base = OpenMeteoCollector.interpolate_temperature_at_elevation(
                elevation_min, current_pressure_temps
            )
            # 验证温度范围 (-50°C 到 50°C)
            current_temp_base = temp_base if (temp_base is not None and -50 < temp_base < 50) else None
            
            elevation_mid = (elevation_min + elevation_max) / 2
            temp_mid = OpenMeteoCollector.interpolate_temperature_at_elevation(
                elevation_mid, current_pressure_temps
            )
            current_temp_mid = temp_mid if (temp_mid is not None and -50 < temp_mid < 50) else None
            
            temp_summit = OpenMeteoCollector.interpolate_temperature_at_elevation(
                elevation_max, current_pressure_temps
            )
            current_temp_summit = temp_summit if (temp_summit is not None and -50 < temp_summit < 50) else None
        
        # 未来24小时平均冰冻高度
        avg_freezing_level_24h = None
        if freezing_levels and len(freezing_levels) >= 24:
            avg_freezing_level_24h = round(sum(freezing_levels[:24]) / 24, 1)
        
        # 未来24小时平均风速
        avg_windspeed_24h = None
        if windspeeds and len(windspeeds) >= 24:
            avg_windspeed_24h = round(sum(windspeeds[:24]) / 24, 1)
        
        # 未来24小时降雪量总和
        snowfall_24h = None
        if snowfalls and len(snowfalls) >= 24:
            snowfall_24h = round(sum(snowfalls[:24]), 1)  # cm
        
        # 未来24小时降水量总和
        precipitation_24h = None
        if precipitations and len(precipitations) >= 24:
            precipitation_24h = round(sum(precipitations[:24]), 1)  # mm
        
        # 未来80小时的详细数据（从当前小时开始）
        hourly_forecast = []
        times = hourly.get('time', [])
        
        # Open-Meteo API 配置说明：
        # - 使用 timezone='auto' 参数时，API 返回雪场当地时区的时间
        # - 返回的时间格式为 "2024-11-23T19:00"（无时区标记，表示当地时间）
        # - API 已经自动从当前时间开始返回未来的小时数据
        # - 因此我们直接从索引 0 开始取数据即可，无需手动查找起始索引
        
        # 从索引 0 开始，取 80 小时数据（约 3.3 天，比 72 小时多一点）
        for i in range(min(80, len(times))):
            forecast_item = {
                'time': times[i] if i < len(times) else None,
                'temperature': temperatures[i] if i < len(temperatures) else None,
                'apparent_temperature': apparent_temperatures[i] if i < len(apparent_temperatures) else None,  # 体感温度
                'humidity': humidities[i] if i < len(humidities) else None,
                'windspeed': windspeeds[i] if i < len(windspeeds) else None,
                'winddirection': winddirections[i] if i < len(winddirections) else None,
                'freezing_level': freezing_levels[i] if i < len(freezing_levels) else None,
                'weather_code': weathercodes[i] if i < len(weathercodes) else None,
                'snowfall': snowfalls[i] if i < len(snowfalls) else None,  # cm
                'precipitation': precipitations[i] if i < len(precipitations) else None,  # mm
            }
            
            # 添加分层温度（如果有海拔数据）
            if elevation_min and elevation_max:
                pressure_temps_hour = {
                    '1000hPa': temp_1000hPa[i] if i < len(temp_1000hPa) else None,
                    '925hPa': temp_925hPa[i] if i < len(temp_925hPa) else None,
                    '850hPa': temp_850hPa[i] if i < len(temp_850hPa) else None,
                    '700hPa': temp_700hPa[i] if i < len(temp_700hPa) else None,
                    '500hPa': temp_500hPa[i] if i < len(temp_500hPa) else None,
                }
                
                # 计算分层温度并验证
                temp_b = OpenMeteoCollector.interpolate_temperature_at_elevation(
                    elevation_min, pressure_temps_hour
                )
                forecast_item['temp_base'] = temp_b if (temp_b is not None and -50 < temp_b < 50) else None
                
                temp_m = OpenMeteoCollector.interpolate_temperature_at_elevation(
                    elevation_mid, pressure_temps_hour
                )
                forecast_item['temp_mid'] = temp_m if (temp_m is not None and -50 < temp_m < 50) else None
                
                temp_s = OpenMeteoCollector.interpolate_temperature_at_elevation(
                    elevation_max, pressure_temps_hour
                )
                forecast_item['temp_summit'] = temp_s if (temp_s is not None and -50 < temp_s < 50) else None
            
            hourly_forecast.append(forecast_item)
        
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
            
            # 从hourly数据中提取每天的天气代码（取中午12点的）
            hourly_times = hourly.get('time', [])
            hourly_weathercodes = hourly.get('weathercode', [])
            
            for i in range(min(7, len(times))):
                date = times[i] if i < len(times) else None
                
                # 找到该日期中午12点的天气代码
                weather_code = None
                if date and hourly_times and hourly_weathercodes:
                    target_time = f"{date}T12:00"
                    try:
                        idx = hourly_times.index(target_time)
                        weather_code = hourly_weathercodes[idx] if idx < len(hourly_weathercodes) else None
                    except ValueError:
                        # 如果找不到12点，就找最接近的时间
                        for j, t in enumerate(hourly_times):
                            if t.startswith(date):
                                weather_code = hourly_weathercodes[j] if j < len(hourly_weathercodes) else None
                                break
                
                forecast_7d.append({
                    'date': date,
                    'temp_max': temps_max[i] if i < len(temps_max) else None,
                    'temp_min': temps_min[i] if i < len(temps_min) else None,
                    'snowfall': snowfall[i] if i < len(snowfall) else None,
                    'precipitation': precipitation[i] if i < len(precipitation) else None,
                    'weather_code': weather_code,  # 添加天气代码
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
                'apparent_temperature': current_apparent_temp,  # 体感温度
                'humidity': current_humidity,
                'windspeed': current_windspeed,
                'winddirection': current_winddirection,
                'winddirection_compass': wind_direction_to_compass(current_winddirection),
            },
            # 冰冻线
            'freezing_level_current': current_freezing_level,
            'freezing_level_24h_avg': avg_freezing_level_24h,
            # 按海拔的温度
            'temp_base': current_temp_base,
            'temp_mid': current_temp_mid,
            'temp_summit': current_temp_summit,
            # 降雪量和降水量预测
            'snowfall_24h': snowfall_24h,  # 未来24小时降雪量总和 (cm)
            'precipitation_24h': precipitation_24h,  # 未来24小时降水量总和 (mm)
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

