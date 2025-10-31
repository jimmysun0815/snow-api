#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪场数据管理器
协调数据采集、标准化和存储
"""

import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from collectors import MtnPowderCollector, OnTheSnowCollector, OpenMeteoCollector
from normalizer import DataNormalizer
from db_manager import DatabaseManager


class ResortDataManager:
    """雪场数据管理器"""
    
    def __init__(self, config_file: str = 'resorts_config.json', data_dir: str = 'data', use_db: bool = True):
        """
        初始化管理器
        
        Args:
            config_file: 配置文件路径
            data_dir: 数据存储目录
            use_db: 是否使用数据库（默认True）
        """
        self.config_file = config_file
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.use_db = use_db
        
        # 加载配置
        self.config = self._load_config()
        self.resorts = self.config.get('resorts', [])
        
        # 初始化数据库管理器
        if self.use_db:
            try:
                self.db_manager = DatabaseManager()
                print("✅ 数据库管理器初始化成功")
            except Exception as e:
                print(f"⚠️  数据库连接失败，将只保存到 JSON 文件: {e}")
                self.use_db = False
                self.db_manager = None
        else:
            self.db_manager = None
        
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"错误: 配置文件 {self.config_file} 不存在")
            return {}
        except json.JSONDecodeError as e:
            print(f"错误: 配置文件解析失败: {e}")
            return {}
    
    def get_collector(self, resort_config: Dict):
        """
        根据配置获取对应的采集器
        
        Args:
            resort_config: 雪场配置
            
        Returns:
            采集器实例
        """
        data_source = resort_config.get('data_source')
        
        if data_source == 'mtnpowder':
            return MtnPowderCollector(resort_config)
        elif data_source == 'onthesnow':
            return OnTheSnowCollector(resort_config)
        else:
            raise ValueError(f"不支持的数据源: {data_source}")
    
    def collect_resort_data(self, resort_config: Dict, include_weather: bool = True) -> Optional[Dict]:
        """
        采集单个雪场数据
        
        Args:
            resort_config: 雪场配置
            include_weather: 是否同时采集天气数据（包括 freezing level）
            
        Returns:
            标准化后的数据或 None
        """
        # 获取采集器
        collector = self.get_collector(resort_config)
        
        # 采集原始数据
        raw_data = collector.collect()
        
        if raw_data is None:
            return None
        
        # 标准化数据
        data_source = resort_config.get('data_source')
        normalized_data = DataNormalizer.normalize(resort_config, raw_data, data_source)
        
        # 同时采集天气数据
        if include_weather:
            weather_collector = OpenMeteoCollector(resort_config)
            weather_raw_data = weather_collector.collect()
            
            if weather_raw_data:
                weather_normalized = DataNormalizer.normalize(
                    resort_config, 
                    weather_raw_data, 
                    'openmeteo'
                )
                
                # 合并天气数据到雪场数据中
                if weather_normalized:
                    normalized_data['weather'] = {
                        'current': weather_normalized.get('current'),
                        'freezing_level_current': weather_normalized.get('freezing_level_current'),
                        'freezing_level_24h_avg': weather_normalized.get('freezing_level_24h_avg'),
                        'temp_base': weather_normalized.get('temp_base'),
                        'temp_mid': weather_normalized.get('temp_mid'),
                        'temp_summit': weather_normalized.get('temp_summit'),
                        'today': weather_normalized.get('today'),
                        'hourly_forecast': weather_normalized.get('hourly_forecast'),
                        'forecast_7d': weather_normalized.get('forecast_7d'),
                        'avg_windspeed_24h': weather_normalized.get('avg_windspeed_24h'),
                        'last_update': weather_normalized.get('last_update')
                    }
                    
                    # 添加雪场海拔信息（如果配置中有）
                    if 'elevation_min' in resort_config and 'elevation_max' in resort_config:
                        normalized_data['elevation'] = {
                            'min': resort_config.get('elevation_min'),
                            'max': resort_config.get('elevation_max'),
                            'vertical': resort_config.get('elevation_max', 0) - resort_config.get('elevation_min', 0)
                        }
        
        return normalized_data
    
    def collect_all(self, enabled_only: bool = True) -> List[Dict]:
        """
        采集所有雪场数据
        
        Args:
            enabled_only: 是否只采集已启用的雪场
            
        Returns:
            标准化数据列表
        """
        results = []
        
        resorts_to_collect = [
            r for r in self.resorts 
            if not enabled_only or r.get('enabled', False)
        ]
        
        print(f"\n开始采集 {len(resorts_to_collect)} 个雪场的数据")
        print("=" * 70)
        print()
        
        for resort_config in resorts_to_collect:
            resort_name = resort_config.get('name')
            print(f"📍 采集: {resort_name}")
            
            try:
                data = self.collect_resort_data(resort_config)
                
                if data:
                    results.append(data)
                    
                    # 保存到数据库
                    if self.use_db and self.db_manager:
                        success = self.db_manager.save_resort_data(resort_config, data)
                        if success:
                            print(f"   ✅ 成功（已存入数据库）")
                        else:
                            print(f"   ✅ 成功（数据库保存失败，仅保存到文件）")
                    else:
                        print(f"   ✅ 成功")
                else:
                    print(f"   ❌ 失败")
                    
            except Exception as e:
                print(f"   ❌ 错误: {e}")
            
            print()
        
        print("=" * 70)
        print(f"采集完成: 成功 {len(results)}/{len(resorts_to_collect)}")
        print()
        
        return results
    
    def save_data(self, data: List[Dict], filename: Optional[str] = None):
        """
        保存数据到文件
        
        Args:
            data: 数据列表
            filename: 文件名（不指定则自动生成）
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'resorts_data_{timestamp}.json'
        
        filepath = self.data_dir / filename
        
        # 添加元数据
        output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_resorts': len(data),
                'version': '1.0'
            },
            'resorts': data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"💾 数据已保存到: {filepath}")
        
        # 同时保存一份为 latest.json 供 API 使用
        latest_path = self.data_dir / 'latest.json'
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"💾 最新数据: {latest_path}")
    
    def load_latest_data(self) -> Optional[Dict]:
        """
        加载最新的数据
        
        Returns:
            数据字典或 None
        """
        latest_path = self.data_dir / 'latest.json'
        
        if not latest_path.exists():
            return None
        
        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载数据失败: {e}")
            return None
    
    def get_resort_by_id(self, resort_id: int) -> Optional[Dict]:
        """
        根据 ID 获取雪场数据
        
        Args:
            resort_id: 雪场 ID
            
        Returns:
            雪场数据或 None
        """
        data = self.load_latest_data()
        
        if not data:
            return None
        
        for resort in data.get('resorts', []):
            if resort.get('resort_id') == resort_id:
                return resort
        
        return None
    
    def get_resort_by_slug(self, slug: str) -> Optional[Dict]:
        """
        根据 slug 获取雪场数据
        
        Args:
            slug: 雪场 slug
            
        Returns:
            雪场数据或 None
        """
        # 从配置中查找
        resort_config = None
        for r in self.resorts:
            if r.get('slug') == slug:
                resort_config = r
                break
        
        if not resort_config:
            return None
        
        # 从最新数据中获取
        return self.get_resort_by_id(resort_config.get('id'))

