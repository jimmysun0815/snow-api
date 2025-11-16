#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪场数据管理器
协调数据采集、标准化和存储
"""

import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
        # Only create directory if not in Lambda environment
        if os.path.exists('/tmp') and not os.path.exists('/var/task'):
            # Local environment
            self.data_dir.mkdir(exist_ok=True)
        self.use_db = use_db
        
        # 加载配置
        self.config = self._load_config()
        self.resorts = self.config.get('resorts', [])
        
        # 初始化数据库管理器
        if self.use_db:
            try:
                self.db_manager = DatabaseManager()
                print("[OK] 数据库管理器初始化成功")
            except Exception as e:
                print(f"[WARNING]  数据库连接失败，将只保存到 JSON 文件: {e}")
                self.use_db = False
                self.db_manager = None
        else:
            self.db_manager = None
        
        # 线程锁，用于保护输出
        self.print_lock = threading.Lock()
        
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
        采集单个雪场数据（支持多数据源）
        
        Args:
            resort_config: 雪场配置
            include_weather: 是否同时采集天气数据（包括 freezing level）
            
        Returns:
            标准化后的数据或 None
        """
        # 1. 采集主数据源
        collector = self.get_collector(resort_config)
        raw_data = collector.collect()
        
        if raw_data is None:
            return None
        
        # 标准化主数据源数据
        data_source = resort_config.get('data_source')
        normalized_data = DataNormalizer.normalize(resort_config, raw_data, data_source)
        
        # 2. 采集 OnTheSnow 补充数据（如果配置了且不是主源）
        onthesnow_url = resort_config.get('onthesnow_url')
        onthesnow_enabled = resort_config.get('onthesnow_enabled', True)
        
        if onthesnow_url and onthesnow_enabled and data_source != 'onthesnow':
            try:
                # 创建临时配置用于 OnTheSnow 采集
                onthesnow_config = {
                    **resort_config,
                    'source_url': onthesnow_url
                }
                
                onthesnow_collector = OnTheSnowCollector(onthesnow_config)
                onthesnow_raw_data = onthesnow_collector.collect()
                
                if onthesnow_raw_data:
                    onthesnow_normalized = DataNormalizer.normalize(
                        onthesnow_config,
                        onthesnow_raw_data,
                        'onthesnow'
                    )
                    
                    # 合并 OnTheSnow 的 webcam 数据
                    if onthesnow_normalized and 'webcams' in onthesnow_normalized:
                        normalized_data['webcams'] = onthesnow_normalized['webcams']
                        
                    # 可选：如果主源数据缺失，用 OnTheSnow 数据补充
                    # 例如：如果主源没有 trails_total，用 OnTheSnow 的
                    if not normalized_data.get('trails_total') and onthesnow_normalized.get('trails_total'):
                        normalized_data['trails_total'] = onthesnow_normalized['trails_total']
                        normalized_data['trails_open'] = onthesnow_normalized.get('trails_open', 0)
                    
            except Exception as e:
                # OnTheSnow 采集失败不影响主数据
                print(f"[WARNING] OnTheSnow 补充数据采集失败: {e}")
        
        # 3. 同时采集天气数据
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
    
    def _collect_single_resort(self, resort_config: Dict, failure_tracker=None) -> tuple[Optional[Dict], Optional[str]]:
        """
        采集单个雪场数据（用于并发）
        
        Args:
            resort_config: 雪场配置
            failure_tracker: 失败追踪器（可选）
            
        Returns:
            (数据, 错误信息) 元组
        """
        resort_name = resort_config.get('name')
        resort_id = resort_config.get('id')
        
        try:
            data = self.collect_resort_data(resort_config)
            
            if data:
                # 保存到数据库
                if self.use_db and self.db_manager:
                    success = self.db_manager.save_resort_data(resort_config, data)
                    if success:
                        with self.print_lock:
                            print(f"   ✅ {resort_name} - 成功（已存入数据库）")
                        return (data, None)
                    else:
                        # 数据库保存失败，视为采集失败
                        with self.print_lock:
                            print(f"   ❌ {resort_name} - 失败（数据库保存失败）")
                        
                        # 记录失败
                        if failure_tracker:
                            url = resort_config.get('source_url', 'N/A')
                            failure_tracker.add_failure(
                                resort_id=resort_id,
                                resort_name=resort_name,
                                error_type='DATABASE_SAVE_FAILED',
                                error_message='数据采集成功但数据库保存失败',
                                url=url
                            )
                        
                        return (None, 'DATABASE_SAVE_FAILED')
                else:
                    # 无数据库连接，仅返回数据用于文件保存
                    with self.print_lock:
                        print(f"   ✅ {resort_name} - 成功")
                    return (data, None)
            else:
                with self.print_lock:
                    print(f"   ❌ {resort_name} - 失败（无数据）")
                
                # 记录失败
                if failure_tracker:
                    url = resort_config.get('source_url', 'N/A')
                    failure_tracker.add_failure(
                        resort_id=resort_id,
                        resort_name=resort_name,
                        error_type='NO_DATA',
                        error_message='采集器返回空数据',
                        url=url
                    )
                
                return (None, 'NO_DATA')
                
        except Exception as e:
            error_str = str(e)
            with self.print_lock:
                print(f"   ❌ {resort_name} - 错误: {error_str[:100]}")
            
            # 记录失败
            if failure_tracker:
                url = resort_config.get('source_url', 'N/A')
                
                # 判断错误类型
                error_type = 'UNKNOWN'
                if '404' in error_str or 'Not Found' in error_str:
                    error_type = 'HTTP_404'
                elif 'timeout' in error_str.lower() or 'timed out' in error_str.lower():
                    error_type = 'TIMEOUT'
                elif 'connection' in error_str.lower():
                    error_type = 'CONNECTION_ERROR'
                elif 'json' in error_str.lower():
                    error_type = 'JSON_ERROR'
                
                failure_tracker.add_failure(
                    resort_id=resort_id,
                    resort_name=resort_name,
                    error_type=error_type,
                    error_message=error_str[:200],  # 限制长度
                    url=url
                )
            
            return (None, error_str)
    
    def collect_all(self, enabled_only: bool = True, failure_tracker=None, max_workers: int = 10) -> List[Dict]:
        """
        采集所有雪场数据（使用多线程并发）
        
        Args:
            enabled_only: 是否只采集已启用的雪场
            failure_tracker: 失败追踪器（可选）
            max_workers: 最大并发线程数（默认10，平衡速度和稳定性）
            
        Returns:
            标准化数据列表
        """
        results = []
        
        resorts_to_collect = [
            r for r in self.resorts 
            if not enabled_only or r.get('enabled', False)
        ]
        
        print(f"\n🚀 开始并发采集 {len(resorts_to_collect)} 个雪场的数据（{max_workers} 线程）")
        print("=" * 70)
        print()
        
        # 使用线程池并发采集
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_resort = {
                executor.submit(self._collect_single_resort, resort_config, failure_tracker): resort_config
                for resort_config in resorts_to_collect
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_resort):
                completed += 1
                data, error = future.result()
                
                if data:
                    results.append(data)
                
                # 显示进度
                with self.print_lock:
                    print(f"   [{completed}/{len(resorts_to_collect)}] 已完成")
        
        print()
        print("=" * 70)
        print(f"✅ 采集完成: 成功 {len(results)}/{len(resorts_to_collect)}")
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
        
        # 只在非 Lambda 环境保存文件
        if not os.path.exists('/var/task'):
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
            
            print(f"[OK] 数据已保存到: {filepath}")
            
            # 同时保存一份为 latest.json 供 API 使用
            latest_path = self.data_dir / 'latest.json'
            with open(latest_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"[OK] 最新数据: {latest_path}")
        else:
            print("[INFO] Lambda 环境，跳过文件保存，数据已存入数据库")
    
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

