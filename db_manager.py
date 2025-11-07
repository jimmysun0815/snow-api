#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Database Manager - Handles data storage, queries and caching

import json
import redis
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional

from config import Config
from models import Base, Resort, ResortCondition, ResortWeather, ResortTrail


class DatabaseManager:
    """数据库和缓存管理器"""
    
    def __init__(self):
        """初始化数据库连接和Redis"""
        # PostgreSQL
        self.engine = create_engine(Config.DATABASE_URL, echo=False, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Redis
        self.redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.cache_ttl = Config.CACHE_TTL
        
        print(f"[OK] 数据库连接成功: {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}")
        print(f"[OK] Redis 连接成功: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    
    def save_resort_data(self, resort_config: Dict, normalized_data: Dict):
        """
        保存雪场数据到数据库
        
        Args:
            resort_config: 雪场配置
            normalized_data: 标准化后的数据
        """
        try:
            # 1. 确保雪场记录存在
            resort = self.session.query(Resort).filter_by(id=resort_config['id']).first()
            
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
                    notes=resort_config.get('notes')
                )
                self.session.add(resort)
            else:
                # 更新雪场基本信息
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
            self.session.add(condition)
            
            # 3. 保存天气数据
            weather_data = normalized_data.get('weather', {})
            if weather_data:
                current = weather_data.get('current', {})
                today = weather_data.get('today', {})
                
                weather = ResortWeather(
                    resort_id=resort_config['id'],
                    timestamp=datetime.now(),
                    current_temp=current.get('temperature'),
                    current_humidity=current.get('humidity'),
                    current_windspeed=current.get('windspeed'),
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
                self.session.add(weather)
            
            # 4. 提交事务
            self.session.commit()
            
            # 5. 清除相关缓存
            self._invalidate_cache(resort_config['id'], resort_config['slug'])
            
            return True
            
        except Exception as e:
            self.session.rollback()
            print(f"[ERROR] 保存数据失败 ({resort_config['name']}): {e}")
            return False
    
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
            }
            
            # 添加雪况数据
            if latest_condition:
                data.update({
                    'status': latest_condition.status,
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
                    'opening_date': latest_condition.extra_data.get('opening_date') if latest_condition.extra_data else None,
                    'last_update': latest_condition.timestamp.isoformat(),
                    'data_source': latest_condition.data_source
                })
            
            # 添加天气数据
            if latest_weather:
                data['weather'] = {
                    'temperature': latest_weather.current_temp,
                    'humidity': latest_weather.current_humidity,
                    'current': {
                        'temperature': latest_weather.current_temp,
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
    
    def get_all_resorts_data(self) -> List[Dict]:
        """
        获取所有雪场的最新数据
        
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
            print(f"[ERROR] 保存雪道数据失败: {e}")
            return False
    
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
    
    def _invalidate_trails_cache(self, resort_id: int, resort_slug: str):
        """清除雪道缓存"""
        self.redis_client.delete(f"trails:{resort_id}")
        self.redis_client.delete(f"trails:{resort_slug}")
    
    def close(self):
        """关闭连接"""
        self.session.close()
        self.redis_client.close()

