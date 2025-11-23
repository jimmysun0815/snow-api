#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Database Manager - Handles data storage, queries and caching

import json
import redis
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from typing import List, Dict, Optional
import threading

from config import Config
from models import Base, Resort, ResortCondition, ResortWeather, ResortTrail, ResortWebcam


def calculate_status_by_opening_date(opening_date_str: str, original_status: str) -> str:
    """
    根据开放日期计算雪场状态（与前端逻辑保持一致）
    
    Args:
        opening_date_str: 开放日期字符串 (ISO格式)
        original_status: 原始状态 (从数据源获取的状态)
    
    Returns:
        计算后的状态: 'open' 或 'closed'
    """
    if not opening_date_str:
        return original_status
    
    try:
        opening_date = datetime.fromisoformat(opening_date_str.replace('Z', '+00:00'))
        now = datetime.now(opening_date.tzinfo) if opening_date.tzinfo else datetime.now()
        difference = (opening_date.date() - now.date()).days
        
        # 如果当前日期在开放日期之后
        if difference < 0:
            days_since_opening = -difference
            # 开放50天内认为是开放状态
            if days_since_opening <= 50:
                return 'open'
            # 超过50天，不显示状态（但为了兼容，返回原始状态）
            return original_status
        
        # 还没到开放日期，返回关闭
        return 'closed'
    except (ValueError, AttributeError) as e:
        # 日期解析失败，返回原始状态
        print(f"[WARN] 解析开放日期失败: {opening_date_str}, error: {e}")
        return original_status


class DatabaseManager:
    """数据库和缓存管理器（线程安全）"""
    
    def __init__(self):
        """初始化数据库连接和Redis"""
        # PostgreSQL - 使用 scoped_session 实现线程安全
        self.engine = create_engine(
            Config.DATABASE_URL, 
            echo=False, 
            pool_pre_ping=True,
            pool_size=20,  # 增加连接池大小以支持并发
            max_overflow=10
        )
        Base.metadata.create_all(self.engine)
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)  # 线程安全的 session
        
        # Redis
        self.redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.cache_ttl = Config.CACHE_TTL
        
        print(f"[OK] 数据库连接成功: {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}")
        print(f"[OK] Redis 连接成功: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
        print(f"[OK] 线程安全模式已启用 (pool_size=20)")
    
    @property
    def session(self):
        """获取当前线程的 session"""
        return self.Session()
    
    def save_resort_data(self, resort_config: Dict, normalized_data: Dict):
        """
        保存雪场数据到数据库（线程安全）
        
        Args:
            resort_config: 雪场配置
            normalized_data: 标准化后的数据
        """
        session = self.Session()  # 获取当前线程的 session
        try:
            # 1. 确保雪场记录存在
            resort = session.query(Resort).filter_by(id=resort_config['id']).first()
            
            if not resort:
                # 创建新雪场记录
                resort = Resort(
                    id=resort_config['id'],
                    name=resort_config['name'],
                    slug=resort_config['slug'],
                    location=resort_config.get('location'),
                    lat=resort_config.get('lat'),
                    lon=resort_config.get('lon'),
                    elevation_min=resort_config.get('elevation_min'),
                    elevation_max=resort_config.get('elevation_max'),
                    data_source=resort_config.get('data_source'),
                    source_url=resort_config.get('source_url'),
                    source_id=resort_config.get('source_id'),
                    enabled=resort_config.get('enabled', True),
                    notes=resort_config.get('notes'),
                    address=normalized_data.get('address'),
                    city=normalized_data.get('city'),
                    zip_code=normalized_data.get('zip_code'),
                    phone=normalized_data.get('phone'),
                    website=normalized_data.get('website')
                )
                session.add(resort)
            else:
                # 更新雪场基本信息（但不更新联系信息，联系信息由 collect_trails 更新）
                resort.updated_at = datetime.now()
            
            # 2. 保存雪况数据
            condition = ResortCondition(
                resort_id=resort_config['id'],
                timestamp=datetime.now(),
                status=normalized_data.get('status'),
                new_snow=normalized_data.get('new_snow', 0),
                base_depth=normalized_data.get('base_depth', 0),
                lifts_open=normalized_data.get('lifts_open', 0),
                lifts_total=normalized_data.get('lifts_total', 0),
                trails_open=normalized_data.get('trails_open', 0),
                trails_total=normalized_data.get('trails_total', 0),
                temperature=normalized_data.get('temperature'),
                source=normalized_data.get('source'),
                data_source=normalized_data.get('data_source'),
                extra_data={
                    'opening_date': normalized_data.get('opening_date'),
                    'closing_date': normalized_data.get('closing_date'),
                    'elevation': normalized_data.get('elevation')
                }
            )
            session.add(condition)
            
            # 3. 保存天气数据
            weather_data = normalized_data.get('weather', {})
            if weather_data:
                current = weather_data.get('current', {})
                today = weather_data.get('today', {})
                
                weather = ResortWeather(
                    resort_id=resort_config['id'],
                    timestamp=datetime.now(),
                    current_temp=current.get('temperature'),
                    apparent_temperature=current.get('apparent_temperature'),
                    current_humidity=current.get('humidity'),
                    current_windspeed=current.get('windspeed'),
                    wind_speed=current.get('windspeed'),
                    wind_direction=current.get('winddirection_compass'),
                    current_winddirection=current.get('winddirection'),
                    current_winddirection_compass=current.get('winddirection_compass'),
                    freezing_level_current=weather_data.get('freezing_level_current'),
                    freezing_level_24h_avg=weather_data.get('freezing_level_24h_avg'),
                    temp_base=weather_data.get('temp_base'),
                    temp_mid=weather_data.get('temp_mid'),
                    temp_summit=weather_data.get('temp_summit'),
                    today_sunrise=today.get('sunrise'),
                    today_sunset=today.get('sunset'),
                    today_temp_max=today.get('temp_max'),
                    today_temp_min=today.get('temp_min'),
                    hourly_forecast=weather_data.get('hourly_forecast'),
                    forecast_7d=weather_data.get('forecast_7d'),
                    source=weather_data.get('source')
                )
                session.add(weather)
            
            # 4. 保存 webcam 数据
            webcams = normalized_data.get('webcams', [])
            if webcams:
                self._save_webcams(session, resort_config['id'], webcams, normalized_data.get('source'))
            
            # 5. 提交事务
            session.commit()
            
            # 6. 清除相关缓存
            self._invalidate_cache(resort_config['id'], resort_config['slug'])
            
            return True
            
        except Exception as e:
            session.rollback()
            import traceback
            print(f"[ERROR] 保存数据失败 ({resort_config['name']}): {e}")
            traceback.print_exc()
            return False
        finally:
            session.close()  # 确保关闭 session
    
    def get_latest_resort_data(self, resort_id: int = None, resort_slug: str = None) -> Optional[Dict]:
        """
        获取雪场最新数据
        
        Args:
            resort_id: 雪场 ID
            resort_slug: 雪场 slug
            
        Returns:
            雪场数据字典或 None
        """
        # 确定查询标识
        cache_key = f"resort:{resort_slug or resort_id}"
        
        # 1. 尝试从 Redis 获取
        cached = self.redis_client.get(cache_key)
        if cached:
            print(f"[OK] 从缓存获取: {cache_key}")
            return json.loads(cached)
        
        # 2. 从数据库查询
        try:
            # 查询雪场基本信息
            if resort_id:
                resort = self.session.query(Resort).filter_by(id=resort_id).first()
            elif resort_slug:
                resort = self.session.query(Resort).filter_by(slug=resort_slug).first()
            else:
                return None
            
            if not resort:
                return None
            
            # 查询最新雪况
            latest_condition = self.session.query(ResortCondition).filter_by(
                resort_id=resort.id
            ).order_by(desc(ResortCondition.timestamp)).first()
            
            # 查询最新天气
            latest_weather = self.session.query(ResortWeather).filter_by(
                resort_id=resort.id
            ).order_by(desc(ResortWeather.timestamp)).first()
            
            # 组装数据
            data = {
                'id': resort.id,  # 添加 'id' 字段用于 API 返回
                'resort_id': resort.id,
                'name': resort.name,
                'slug': resort.slug,
                'location': resort.location,
                'lat': resort.lat,
                'lon': resort.lon,
                'elevation_min': resort.elevation_min,
                'elevation_max': resort.elevation_max,
                'elevation': {
                    'min': resort.elevation_min,
                    'max': resort.elevation_max,
                    'vertical': (resort.elevation_max or 0) - (resort.elevation_min or 0)
                } if resort.elevation_min and resort.elevation_max else None,
                # 联系信息
                'address': resort.address,
                'city': resort.city,
                'zip_code': resort.zip_code,
                'phone': resort.phone,
                'website': resort.website,
                # 营业时间
                'opening_hours': {
                    'weekday_text': json.loads(resort.opening_hours_weekday) if resort.opening_hours_weekday else None,
                    'periods': resort.opening_hours_data,
                    'open_now': resort.is_open_now
                } if resort.opening_hours_weekday or resort.opening_hours_data else None,
            }
            
            # 添加雪况数据
            if latest_condition:
                # 获取开放日期
                opening_date = latest_condition.extra_data.get('opening_date') if latest_condition.extra_data else None
                
                # 基于开放日期计算状态（与前端和列表页逻辑一致）
                calculated_status = calculate_status_by_opening_date(opening_date, latest_condition.status)
                
                data.update({
                    'status': calculated_status,  # 使用计算后的状态
                    'new_snow': latest_condition.new_snow,
                    'new_snow_24h': latest_condition.new_snow,
                    'new_snow_48h': latest_condition.extra_data.get('new_snow_48h') if latest_condition.extra_data else None,
                    'base_depth': latest_condition.base_depth,
                    'snow_depth_base': latest_condition.base_depth,
                    'snow_depth_summit': latest_condition.extra_data.get('summit_depth') if latest_condition.extra_data else None,
                    'lifts_open': latest_condition.lifts_open,
                    'lifts_total': latest_condition.lifts_total,
                    'trails_open': latest_condition.trails_open,
                    'trails_total': latest_condition.trails_total,
                    'temperature': latest_condition.temperature,
                    'opening_date': opening_date,
                    'last_update': latest_condition.timestamp.isoformat(),
                    'data_source': latest_condition.data_source
                })
            
            # 添加天气数据
            if latest_weather:
                data['weather'] = {
                    'temperature': latest_weather.current_temp,
                    'apparent_temperature': latest_weather.apparent_temperature,
                    'humidity': latest_weather.current_humidity,
                    'wind_speed': latest_weather.wind_speed,
                    'wind_direction': latest_weather.wind_direction,
                    'current': {
                        'temperature': latest_weather.current_temp,
                        'apparent_temperature': latest_weather.apparent_temperature,
                        'humidity': latest_weather.current_humidity,
                        'windspeed': latest_weather.current_windspeed,
                        'winddirection': latest_weather.current_winddirection,
                        'winddirection_compass': latest_weather.current_winddirection_compass
                    },
                    'freezing_level_current': latest_weather.freezing_level_current,
                    'freezing_level_24h_avg': latest_weather.freezing_level_24h_avg,
                    'temp_base': latest_weather.temp_base,
                    'temp_mid': latest_weather.temp_mid,
                    'temp_summit': latest_weather.temp_summit,
                    'today': {
                        'sunrise': latest_weather.today_sunrise,
                        'sunset': latest_weather.today_sunset,
                        'temp_max': latest_weather.today_temp_max,
                        'temp_min': latest_weather.today_temp_min
                    },
                    'hourly_forecast': latest_weather.hourly_forecast,
                    'forecast_7d': latest_weather.forecast_7d,
                    'last_update': latest_weather.timestamp.isoformat()
                }
            
            # 查询最新的 webcam 数据（按 webcam_uuid 去重，每个只取最新的）
            # 使用子查询获取每个 webcam_uuid 的最新 timestamp
            from sqlalchemy import func
            latest_webcam_subquery = self.session.query(
                ResortWebcam.webcam_uuid,
                func.max(ResortWebcam.timestamp).label('max_timestamp')
            ).filter(
                ResortWebcam.resort_id == resort.id
            ).group_by(
                ResortWebcam.webcam_uuid
            ).subquery()
            
            latest_webcams = self.session.query(ResortWebcam).join(
                latest_webcam_subquery,
                (ResortWebcam.webcam_uuid == latest_webcam_subquery.c.webcam_uuid) &
                (ResortWebcam.timestamp == latest_webcam_subquery.c.max_timestamp)
            ).filter(
                ResortWebcam.resort_id == resort.id
            ).all()
            
            if latest_webcams:
                data['webcams'] = [
                    {
                        'webcam_uuid': webcam.webcam_uuid,
                        'title': webcam.title,
                        'image_url': webcam.image_url,
                        'thumbnail_url': webcam.thumbnail_url,
                        'video_stream_url': webcam.video_stream_url,
                        'webcam_type': webcam.webcam_type,
                        'is_featured': webcam.is_featured,
                        'last_updated': webcam.last_updated.isoformat() if webcam.last_updated else None,
                        'source': webcam.source
                    }
                    for webcam in latest_webcams
                ]
            
            # 3. 存入 Redis 缓存
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data, ensure_ascii=False)
            )
            
            print(f"[DATA] 从数据库获取并缓存: {resort.name}")
            return data
            
        except Exception as e:
            print(f"[ERROR] 查询数据失败: {e}")
            return None
    
    def get_all_resorts_summary(self) -> List[Dict]:
        """
        获取所有雪场的摘要信息（轻量级，不含完整天气预报）
        
        Returns:
            雪场摘要列表
        """
        cache_key = "resorts:summary"
        
        # 1. 尝试从 Redis 获取
        cached = self.redis_client.get(cache_key)
        if cached:
            print("[OK] 从缓存获取所有雪场摘要")
            return json.loads(cached)
        
        # 2. 从数据库查询
        try:
            resorts = self.session.query(Resort).filter_by(enabled=True).all()
            summary_list = []
            
            for resort in resorts:
                # 查询最新雪况
                latest_condition = self.session.query(ResortCondition).filter_by(
                    resort_id=resort.id
                ).order_by(desc(ResortCondition.timestamp)).first()
                
                # 查询最新天气（只需要当前温度、湿度等基础字段）
                latest_weather = self.session.query(ResortWeather).filter_by(
                    resort_id=resort.id
                ).order_by(desc(ResortWeather.timestamp)).first()
                
                # 组装摘要数据（不包含 hourly_forecast 和 forecast_7d）
                summary = {
                    'id': resort.id,
                    'name': resort.name,
                    'slug': resort.slug,
                    'location': resort.location,
                    'lat': resort.lat,
                    'lon': resort.lon,
                    'elevation_min': resort.elevation_min,
                    'elevation_max': resort.elevation_max,
                    # 联系信息和营业时间（静态数据）
                    'address': resort.address,
                    'city': resort.city,
                    'zip_code': resort.zip_code,
                    'phone': resort.phone,
                    'website': resort.website,
                    'opening_hours_weekday': resort.opening_hours_weekday,
                    'opening_hours_data': resort.opening_hours_data,
                    'is_open_now': resort.is_open_now,
                    'data_source': resort.data_source,
                    'source_url': resort.source_url,
                    'enabled': resort.enabled,
                    'updated_at': resort.updated_at.isoformat() if resort.updated_at else None,
                }
                
                # 添加雪况信息
                if latest_condition:
                    # 获取开放日期
                    opening_date = latest_condition.extra_data.get('opening_date') if latest_condition.extra_data else None
                    
                    # 基于开放日期计算状态（与前端和详情页逻辑一致）
                    calculated_status = calculate_status_by_opening_date(opening_date, latest_condition.status)
                    
                    summary.update({
                        'status': calculated_status,  # 使用计算后的状态
                        'opening_date': opening_date,  # 添加开放日期字段供前端使用
                        'new_snow_24h': latest_condition.new_snow,
                        'base_depth': latest_condition.base_depth,
                        'lifts_open': latest_condition.lifts_open,
                        'lifts_total': latest_condition.lifts_total,
                        'trails_open': latest_condition.trails_open,
                        'trails_total': latest_condition.trails_total,
                        'last_condition_update': latest_condition.timestamp.isoformat(),
                    })
                
                # 添加基础天气信息（不含预报）
                if latest_weather:
                    summary['weather'] = {
                        'temperature': latest_weather.current_temp,
                        'apparent_temperature': latest_weather.apparent_temperature,
                        'humidity': latest_weather.current_humidity,
                        'wind_speed': latest_weather.wind_speed,
                        'wind_direction': latest_weather.wind_direction,
                        'last_weather_update': latest_weather.timestamp.isoformat(),
                    }
                
                summary_list.append(summary)
            
            # 3. 存入 Redis 缓存（缓存时间可以更短，比如10分钟）
            self.redis_client.setex(
                cache_key,
                600,  # 10分钟缓存
                json.dumps(summary_list, ensure_ascii=False)
            )
            
            print(f"[DATA] 从数据库获取 {len(summary_list)} 个雪场摘要并缓存")
            return summary_list
            
        except Exception as e:
            print(f"[ERROR] 查询所有雪场摘要失败: {e}")
            return []
    
    def get_all_resorts_data(self) -> List[Dict]:
        """
        获取所有雪场的最新数据（完整版，包含天气预报）
        
        Returns:
            雪场数据列表
        """
        cache_key = "resorts:all"
        
        # 1. 尝试从 Redis 获取
        cached = self.redis_client.get(cache_key)
        if cached:
            print("[OK] 从缓存获取所有雪场数据")
            return json.loads(cached)
        
        # 2. 从数据库查询
        try:
            resorts = self.session.query(Resort).filter_by(enabled=True).all()
            data_list = []
            
            for resort in resorts:
                data = self.get_latest_resort_data(resort_id=resort.id)
                if data:
                    data_list.append(data)
            
            # 3. 存入 Redis 缓存
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data_list, ensure_ascii=False)
            )
            
            print(f"[DATA] 从数据库获取 {len(data_list)} 个雪场数据并缓存")
            return data_list
            
        except Exception as e:
            print(f"[ERROR] 查询所有雪场数据失败: {e}")
            return []
    
    def save_trails_data(self, resort_config: Dict, trails_data: Dict) -> bool:
        """
        保存雪道数据和边界到数据库
        
        Args:
            resort_config: 雪场配置
            trails_data: 雪道数据（从 OSMTrailsCollector 返回）
            
        Returns:
            是否成功
        """
        try:
            resort_id = resort_config['id']
            
            # 1. 更新雪场边界（如果有）
            boundary = trails_data.get('boundary')
            if boundary:
                resort = self.session.query(Resort).filter_by(id=resort_id).first()
                if resort:
                    resort.boundary = boundary
                    print(f"[OK] 保存边界数据 ({len(boundary)} 个点)")
            
            # 2. 删除该雪场的旧雪道数据
            self.session.query(ResortTrail).filter_by(resort_id=resort_id).delete()
            
            # 3. 保存新雪道数据
            trails = trails_data.get('trails', [])
            
            for trail in trails:
                trail_obj = ResortTrail(
                    resort_id=resort_id,
                    osm_id=trail.get('osm_id'),
                    osm_type=trail.get('osm_type'),
                    name=trail.get('name'),
                    difficulty=trail.get('difficulty'),
                    piste_type=trail.get('piste_type'),
                    geometry=trail.get('geometry'),
                    length_meters=trail.get('length_meters'),
                    lit=trail.get('lit'),
                    grooming=trail.get('grooming'),
                    width=trail.get('width'),
                    ref=trail.get('ref')
                )
                self.session.add(trail_obj)
            
            # 4. 提交事务
            self.session.commit()
            
            # 5. 清除缓存
            self._invalidate_trails_cache(resort_id, resort_config['slug'])
            
            print(f"[OK] 保存 {len(trails)} 条雪道数据")
            return True
            
        except Exception as e:
            self.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"[ERROR] 保存雪道数据失败: {e}")
            print(f"[DEBUG] 详细错误:\n{error_detail}")
            return False
    
    def save_contact_info(self, resort_id: int, contact_info: Dict) -> bool:
        """
        保存或更新雪场的联系信息
        
        Args:
            resort_id: 雪场 ID
            contact_info: 联系信息字典（从 GooglePlacesCollector 返回）
            
        Returns:
            是否成功
        """
        session = self.Session()  # 获取线程安全的 session
        try:
            # 查找雪场
            resort = session.query(Resort).filter_by(id=resort_id).first()
            
            if not resort:
                print(f"[WARNING] 未找到 ID 为 {resort_id} 的雪场")
                return False
            
            # 更新联系信息
            updated_fields = []
            
            # 只使用 street_address，不要fallback到formatted_address
            # formatted_address包含完整地址，会导致格式混乱
            if contact_info.get('street_address'):
                street_addr = contact_info.get('street_address')
                
                # 过滤地址：如果格式是 "City, State Zip, Country"，只保留第一部分
                # 例如："Vail, CO 81657, USA" -> "Vail"
                # 例如："Warren, VT 05674, USA" -> "Warren"
                if ',' in street_addr:
                    # 检查是否是城市级别的地址（包含州、邮编等）
                    parts = [p.strip() for p in street_addr.split(',')]
                    # 如果有多个部分，且第二部分看起来像州代码（2个字母）或包含数字
                    if len(parts) >= 2:
                        second_part = parts[1]
                        # 如果第二部分是州代码格式（如 "CO 81657" 或 "VT 05674"）
                        if any(char.isdigit() for char in second_part) or len(second_part.split()[0]) == 2:
                            # 只保留第一部分（城市名）
                            street_addr = parts[0]
                            print(f"[INFO] 地址过滤: '{contact_info.get('street_address')}' -> '{street_addr}'")
                
                resort.address = street_addr
                updated_fields.append('地址')
            
            if contact_info.get('city'):
                resort.city = contact_info.get('city')
                updated_fields.append('城市')
            
            if contact_info.get('postal_code'):
                resort.zip_code = contact_info.get('postal_code')
                updated_fields.append('邮编')
            
            if contact_info.get('phone'):
                resort.phone = contact_info.get('phone')
                updated_fields.append('电话')
            
            if contact_info.get('website'):
                resort.website = contact_info.get('website')
                updated_fields.append('网站')
            
            # 保存营业时间
            opening_hours = contact_info.get('opening_hours')
            if opening_hours:
                import json as json_module
                # 保存 weekday_text（人类可读格式）
                if opening_hours.get('weekday_text'):
                    resort.opening_hours_weekday = json_module.dumps(opening_hours['weekday_text'], ensure_ascii=False)
                    updated_fields.append('营业时间')
                
                # 保存 periods（详细数据）
                if opening_hours.get('periods'):
                    resort.opening_hours_data = opening_hours['periods']
                
                # 保存当前营业状态
                if 'open_now' in opening_hours:
                    resort.is_open_now = opening_hours['open_now']
                    updated_fields.append('营业状态')
            
            # 可选：更新经纬度（Google Maps 的可能更准确）
            geometry = contact_info.get('geometry')
            if geometry and geometry.get('lat') and geometry.get('lng'):
                resort.lat = geometry.get('lat')
                resort.lon = geometry.get('lng')
                updated_fields.append('坐标')
            
            resort.updated_at = datetime.now()
            
            # 提交事务
            session.commit()
            
            if updated_fields:
                print(f"[OK] 更新了: {', '.join(updated_fields)}")
            else:
                print(f"[INFO] 没有新的联系信息需要更新")
            
            return True
            
        except Exception as e:
            session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"[ERROR] 保存联系信息失败: {e}")
            print(f"[DEBUG] 详细错误:\n{error_detail}")
            return False
        finally:
            session.close()  # 确保关闭 session
    
    def get_resort_trails(self, resort_id: int = None, resort_slug: str = None) -> List[Dict]:
        """
        获取雪场的雪道数据
        
        Args:
            resort_id: 雪场 ID
            resort_slug: 雪场 slug
            
        Returns:
            雪道列表
        """
        # 确定缓存键
        cache_key = f"trails:{resort_slug or resort_id}"
        
        # 1. 尝试从 Redis 获取
        cached = self.redis_client.get(cache_key)
        if cached:
            print(f"[OK] 从缓存获取雪道: {cache_key}")
            return json.loads(cached)
        
        # 2. 从数据库查询
        try:
            # 查询雪场
            if resort_id:
                resort = self.session.query(Resort).filter_by(id=resort_id).first()
            elif resort_slug:
                resort = self.session.query(Resort).filter_by(slug=resort_slug).first()
            else:
                return []
            
            if not resort:
                return []
            
            # 查询雪道
            trails = self.session.query(ResortTrail).filter_by(resort_id=resort.id).all()
            
            # 转换为字典
            trails_data = []
            for trail in trails:
                trails_data.append({
                    'id': trail.id,
                    'osm_id': trail.osm_id,
                    'osm_type': trail.osm_type,
                    'name': trail.name,
                    'difficulty': trail.difficulty,
                    'piste_type': trail.piste_type,
                    'geometry': trail.geometry,
                    'length_meters': trail.length_meters,
                    'lit': trail.lit,
                    'grooming': trail.grooming,
                    'width': trail.width,
                    'ref': trail.ref
                })
            
            # 3. 存入 Redis 缓存（雪道数据不常变，缓存1小时）
            self.redis_client.setex(
                cache_key,
                3600,  # 1小时
                json.dumps(trails_data, ensure_ascii=False)
            )
            
            print(f"[DATA] 从数据库获取 {len(trails_data)} 条雪道并缓存")
            return trails_data
            
        except Exception as e:
            print(f"[ERROR] 查询雪道数据失败: {e}")
            return []
    
    def _invalidate_cache(self, resort_id: int, resort_slug: str):
        """清除相关缓存"""
        self.redis_client.delete(f"resort:{resort_id}")
        self.redis_client.delete(f"resort:{resort_slug}")
        self.redis_client.delete("resorts:all")
    
    def _save_webcams(self, session, resort_id: int, webcams: list, source: str):
        """
        保存 webcam 数据到数据库
        
        Args:
            session: 数据库 session
            resort_id: 雪场 ID
            webcams: webcam 数据列表
            source: 数据来源
        """
        from dateutil import parser as date_parser
        
        timestamp = datetime.now()
        
        for cam in webcams:
            # 解析 last_updated 时间
            last_updated = None
            if cam.get('last_updated'):
                try:
                    last_updated = date_parser.parse(cam['last_updated'])
                except:
                    pass
            
            webcam = ResortWebcam(
                resort_id=resort_id,
                timestamp=timestamp,
                webcam_uuid=cam.get('webcam_uuid'),
                title=cam.get('title'),
                image_url=cam.get('image_url'),
                thumbnail_url=cam.get('thumbnail_url'),
                video_stream_url=cam.get('video_stream_url'),
                webcam_type=cam.get('webcam_type', 0),
                is_featured=cam.get('is_featured', False),
                last_updated=last_updated,
                source=source
            )
            session.add(webcam)
    
    def _invalidate_trails_cache(self, resort_id: int, resort_slug: str):
        """清除雪道缓存"""
        self.redis_client.delete(f"trails:{resort_id}")
        self.redis_client.delete(f"trails:{resort_slug}")
    
    def disable_resort(self, resort_id: int) -> dict:
        """
        禁用雪场（软删除，设置 enabled=false）
        
        ✅ 可恢复的删除操作
        ✅ 不删除任何数据，只标记为禁用
        
        Args:
            resort_id: 雪场 ID
        
        Returns:
            {
                'resort_id': int,
                'resort_name': str,
                'resort_slug': str
            }
        
        Raises:
            ValueError: 雪场不存在
        """
        session = self.Session()
        
        try:
            # 检查雪场是否存在
            resort = session.query(Resort).filter_by(id=resort_id).first()
            
            if not resort:
                session.close()
                raise ValueError(f'雪场 ID {resort_id} 不存在')
            
            resort_slug = resort.slug
            resort_name = resort.name
            
            print(f"🔒 禁用雪场: ID={resort_id}, Name={resort_name}")
            
            # 设置为禁用
            resort.enabled = False
            
            # 提交事务
            session.commit()
            print(f"✅ 雪场已禁用: {resort_name}")
            
            # 清除缓存（这样前端立即看不到这个雪场）
            self._invalidate_cache(resort_id, resort_slug)
            self._invalidate_trails_cache(resort_id, resort_slug)
            print(f"✅ 缓存已清除")
            
            # 返回禁用的雪场信息
            return {
                'resort_id': resort_id,
                'resort_name': resort_name,
                'resort_slug': resort_slug
            }
            
        except ValueError:
            session.close()
            raise
        except Exception as e:
            session.rollback()
            print(f"❌ 禁用雪场失败: {e}")
            raise
        finally:
            session.close()
    
    def delete_resort(self, resort_id: int) -> dict:
        """
        删除雪场及其所有关联数据
        
        ⚠️ 此操作无法恢复！
        
        Args:
            resort_id: 雪场 ID
        
        Returns:
            {
                'resort_id': int,
                'resort_name': str,
                'resort_slug': str
            }
        
        Raises:
            ValueError: 雪场不存在
        """
        session = self.Session()  # 获取当前线程的 session
        
        try:
            # 1. 检查雪场是否存在
            resort = session.query(Resort).filter_by(id=resort_id).first()
            
            if not resort:
                session.close()
                raise ValueError(f'雪场 ID {resort_id} 不存在')
            
            resort_slug = resort.slug
            resort_name = resort.name
            
            print(f"🗑️  开始删除雪场: ID={resort_id}, Name={resort_name}")
            
            # 2. 删除关联数据（按照外键依赖顺序）
            # 删除天气数据
            weather_count = session.query(ResortWeather).filter_by(resort_id=resort_id).delete(synchronize_session=False)
            print(f"   删除 {weather_count} 条天气数据")
            
            # 删除雪况数据
            condition_count = session.query(ResortCondition).filter_by(resort_id=resort_id).delete(synchronize_session=False)
            print(f"   删除 {condition_count} 条雪况数据")
            
            # 删除雪道数据
            trail_count = session.query(ResortTrail).filter_by(resort_id=resort_id).delete(synchronize_session=False)
            print(f"   删除 {trail_count} 条雪道数据")
            
            # 删除摄像头数据
            webcam_count = session.query(ResortWebcam).filter_by(resort_id=resort_id).delete(synchronize_session=False)
            print(f"   删除 {webcam_count} 条摄像头数据")
            
            # Flush 确保关联数据先被删除
            session.flush()
            print(f"   ✅ 关联数据已删除")
            
            # 3. 删除主数据
            session.delete(resort)
            
            # 4. 提交事务
            session.commit()
            print(f"✅ 雪场删除成功: {resort_name}")
            
            # 5. 清除缓存
            self._invalidate_cache(resort_id, resort_slug)
            self._invalidate_trails_cache(resort_id, resort_slug)
            print(f"✅ 缓存已清除")
            
            # 返回删除的雪场信息
            return {
                'resort_id': resort_id,
                'resort_name': resort_name,
                'resort_slug': resort_slug
            }
            
        except ValueError:
            # 雪场不存在，直接抛出
            session.close()
            raise
        except Exception as e:
            session.rollback()
            print(f"❌ 删除雪场失败: {e}")
            raise
        finally:
            session.close()
    
    def close(self):
        """关闭连接"""
        self.session.close()
        self.redis_client.close()

