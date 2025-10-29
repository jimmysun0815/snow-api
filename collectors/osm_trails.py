#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenStreetMap 雪道数据采集器
从 Overpass API 获取雪道数据
"""

from .base import BaseCollector
import requests
from typing import Optional, Dict, List
import math


class OSMTrailsCollector(BaseCollector):
    """OpenStreetMap 雪道数据采集器"""
    
    OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
    
    def collect(self) -> Optional[Dict]:
        """
        采集雪道数据
        
        Returns:
            包含雪道列表的字典或 None
        """
        lat = self.resort_config.get('lat')
        lon = self.resort_config.get('lon')
        
        if not lat or not lon:
            self.log('ERROR', '缺少经纬度信息')
            return None
        
        # 计算搜索范围（约5公里半径的矩形）
        search_radius_km = 5
        bbox = self._calculate_bbox(lat, lon, search_radius_km)
        
        # 构建 Overpass 查询（增加超时到180秒）
        query = f"""
        [out:json][timeout:180];
        (
          way["piste:type"]{bbox};
          relation["piste:type"]{bbox};
        );
        out geom;
        """
        
        self.log('INFO', f'查询雪道数据 (半径: {search_radius_km}km)')
        self.random_delay(1.0, 2.0)
        
        try:
            # Overpass API 需要 POST 请求（增加超时到 200 秒）
            response = requests.post(
                self.OVERPASS_API_URL,
                data={'data': query},
                headers=self.get_headers(),
                timeout=200
            )
            
            if response.status_code != 200:
                self.log('ERROR', f'HTTP {response.status_code}')
                return None
            
            data = response.json()
            
            if 'elements' not in data:
                self.log('ERROR', '响应格式错误')
                return None
            
            elements = data['elements']
            self.log('INFO', f'找到 {len(elements)} 条雪道')
            
            # 处理雪道数据
            trails = self._process_trails(elements, lat, lon)
            
            return {
                'resort_id': self.resort_config.get('id'),
                'resort_name': self.resort_config.get('name'),
                'center_lat': lat,
                'center_lon': lon,
                'search_radius_km': search_radius_km,
                'total_trails': len(trails),
                'trails': trails
            }
            
        except requests.exceptions.Timeout:
            self.log('ERROR', 'API 超时')
            return None
        except Exception as e:
            self.log('ERROR', f'采集失败: {str(e)}')
            return None
    
    def _calculate_bbox(self, lat: float, lon: float, radius_km: float) -> str:
        """
        计算搜索边界框
        
        Args:
            lat: 中心纬度
            lon: 中心经度
            radius_km: 半径（公里）
            
        Returns:
            边界框字符串 "(south,west,north,east)"
        """
        # 简化计算：1度纬度约111公里
        lat_offset = radius_km / 111.0
        lon_offset = radius_km / (111.0 * math.cos(math.radians(lat)))
        
        south = lat - lat_offset
        north = lat + lat_offset
        west = lon - lon_offset
        east = lon + lon_offset
        
        return f"({south},{west},{north},{east})"
    
    def _process_trails(self, elements: List[Dict], center_lat: float, center_lon: float) -> List[Dict]:
        """
        处理雪道数据
        
        Args:
            elements: OSM 元素列表
            center_lat: 中心纬度
            center_lon: 中心经度
            
        Returns:
            处理后的雪道列表
        """
        trails = []
        
        for element in elements:
            trail = self._process_single_trail(element, center_lat, center_lon)
            if trail:
                trails.append(trail)
        
        return trails
    
    def _process_single_trail(self, element: Dict, center_lat: float, center_lon: float) -> Optional[Dict]:
        """处理单条雪道"""
        try:
            tags = element.get('tags', {})
            
            # 提取几何数据
            geometry = []
            if element['type'] == 'way':
                # Way: 使用 geometry 字段
                for node in element.get('geometry', []):
                    geometry.append([node['lon'], node['lat']])
            elif element['type'] == 'relation':
                # Relation: 从成员中提取
                for member in element.get('members', []):
                    if member.get('role') in ['', 'outer'] and 'geometry' in member:
                        for node in member['geometry']:
                            geometry.append([node['lon'], node['lat']])
            
            if not geometry:
                return None
            
            # 计算雪道长度
            length = self._calculate_length(geometry)
            
            # 计算距离中心的距离
            if geometry:
                mid_point = geometry[len(geometry) // 2]
                distance_from_center = self._haversine_distance(
                    center_lat, center_lon,
                    mid_point[1], mid_point[0]
                )
            else:
                distance_from_center = 999
            
            # 组装雪道数据
            trail_data = {
                'osm_id': str(element['id']),
                'osm_type': element['type'],
                'name': tags.get('name', tags.get('ref', f"Trail {element['id']}")),
                'difficulty': tags.get('piste:difficulty', 'unknown'),
                'piste_type': tags.get('piste:type', 'downhill'),
                'geometry': geometry,
                'length_meters': round(length, 2),
                'lit': tags.get('lit') == 'yes',
                'grooming': tags.get('piste:grooming'),
                'width': tags.get('width'),
                'ref': tags.get('ref'),
                'distance_from_center_km': round(distance_from_center, 2)
            }
            
            return trail_data
            
        except Exception as e:
            self.log('WARNING', f'处理雪道失败 (ID: {element.get("id")}): {e}')
            return None
    
    def _calculate_length(self, coordinates: List[List[float]]) -> float:
        """
        计算雪道长度（米）
        
        Args:
            coordinates: 坐标数组 [[lon, lat], ...]
            
        Returns:
            长度（米）
        """
        if len(coordinates) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]
            distance = self._haversine_distance(lat1, lon1, lat2, lon2)
            total_length += distance
        
        return total_length * 1000  # 转换为米
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Haversine 公式计算距离（公里）
        """
        R = 6371  # 地球半径（公里）
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

