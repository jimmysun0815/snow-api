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
            包含雪道列表和边界的字典或 None
        """
        lat = self.resort_config.get('lat')
        lon = self.resort_config.get('lon')
        resort_name = self.resort_config.get('name')
        
        if not lat or not lon:
            self.log('ERROR', '缺少经纬度信息')
            return None
        
        # 步骤1: 获取雪场边界
        self.log('INFO', '步骤1: 获取雪场边界')
        boundary = self._fetch_resort_boundary(resort_name, lat, lon)
        
        if boundary:
            self.log('INFO', f'✓ 找到边界 ({len(boundary)} 个点)')
        else:
            self.log('WARNING', '⚠ 未找到边界，将使用半径过滤')
        
        # 步骤2: 获取雪道数据
        self.log('INFO', '步骤2: 获取雪道数据')
        search_radius_km = 5
        bbox = self._calculate_bbox(lat, lon, search_radius_km)
        
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
            self.log('INFO', f'找到 {len(elements)} 条原始雪道')
            
            # 步骤3: 处理和过滤雪道
            self.log('INFO', '步骤3: 过滤雪道')
            trails = self._process_trails(elements, lat, lon, boundary)
            
            return {
                'resort_id': self.resort_config.get('id'),
                'resort_name': resort_name,
                'center_lat': lat,
                'center_lon': lon,
                'search_radius_km': search_radius_km,
                'boundary': boundary,  # 边界数据
                'total_trails': len(trails),
                'trails': trails
            }
            
        except requests.exceptions.Timeout:
            self.log('ERROR', 'API 超时')
            return None
        except Exception as e:
            self.log('ERROR', f'采集失败: {str(e)}')
            return None
    
    def _fetch_resort_boundary(self, resort_name: str, lat: float, lon: float) -> Optional[List[List[float]]]:
        """
        获取雪场边界
        
        Args:
            resort_name: 雪场名称
            lat: 中心纬度
            lon: 中心经度
            
        Returns:
            边界坐标列表 [[lon, lat], ...] 或 None
        """
        # 搜索范围（10公里）
        bbox = self._calculate_bbox(lat, lon, 10)
        
        # 尝试多种查询策略
        queries = [
            # 策略1: 精确名称匹配
            f"""
            [out:json][timeout:25];
            (
              way["landuse"="winter_sports"]["name"="{resort_name}"]{bbox};
              relation["landuse"="winter_sports"]["name"="{resort_name}"]{bbox};
              area["landuse"="winter_sports"]["name"="{resort_name}"]{bbox};
            );
            out geom;
            """,
            # 策略2: 部分名称匹配
            f"""
            [out:json][timeout:25];
            (
              way["landuse"="winter_sports"]["name"~"{resort_name.split()[0]}.*"]{bbox};
              relation["landuse"="winter_sports"]["name"~"{resort_name.split()[0]}.*"]{bbox};
            );
            out geom;
            """,
            # 策略3: 仅查询 landuse=winter_sports，按距离排序
            f"""
            [out:json][timeout:25];
            (
              way["landuse"="winter_sports"]{bbox};
              relation["landuse"="winter_sports"]{bbox};
            );
            out geom;
            """
        ]
        
        for i, query in enumerate(queries, 1):
            try:
                self.random_delay(0.5, 1.0)
                response = requests.post(
                    self.OVERPASS_API_URL,
                    data={'data': query},
                    headers=self.get_headers(),
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    elements = data.get('elements', [])
                    
                    if elements:
                        self.log('INFO', f'策略{i}找到 {len(elements)} 个边界')
                        # 取最接近中心的边界
                        best_element = self._find_closest_boundary(elements, lat, lon)
                        if best_element:
                            return self._extract_boundary_geometry(best_element)
                            
            except Exception as e:
                self.log('WARNING', f'策略{i}失败: {e}')
                continue
        
        return None
    
    def _find_closest_boundary(self, elements: List[Dict], lat: float, lon: float) -> Optional[Dict]:
        """找到最接近中心点的边界"""
        if not elements:
            return None
        
        if len(elements) == 1:
            return elements[0]
        
        # 计算每个边界的中心点，找最近的
        min_distance = float('inf')
        closest = None
        
        for elem in elements:
            boundary = self._extract_boundary_geometry(elem)
            if boundary and len(boundary) > 0:
                # 计算边界中心
                center_lon = sum(p[0] for p in boundary) / len(boundary)
                center_lat = sum(p[1] for p in boundary) / len(boundary)
                
                distance = self._haversine_distance(lat, lon, center_lat, center_lon)
                if distance < min_distance:
                    min_distance = distance
                    closest = elem
        
        return closest
    
    def _extract_boundary_geometry(self, element: Dict) -> Optional[List[List[float]]]:
        """从OSM元素中提取边界几何"""
        geometry = []
        
        try:
            if element['type'] == 'way':
                for node in element.get('geometry', []):
                    geometry.append([node['lon'], node['lat']])
            elif element['type'] == 'relation':
                # 只取outer成员
                for member in element.get('members', []):
                    if member.get('role') in ['outer', ''] and 'geometry' in member:
                        for node in member['geometry']:
                            geometry.append([node['lon'], node['lat']])
            
            # 确保边界是闭合的
            if geometry and geometry[0] != geometry[-1]:
                geometry.append(geometry[0])
            
            return geometry if len(geometry) >= 3 else None
            
        except Exception as e:
            self.log('WARNING', f'提取边界失败: {e}')
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
    
    def _process_trails(self, elements: List[Dict], center_lat: float, center_lon: float, 
                        boundary: Optional[List[List[float]]] = None) -> List[Dict]:
        """
        处理雪道数据
        
        Args:
            elements: OSM 元素列表
            center_lat: 中心纬度
            center_lon: 中心经度
            boundary: 雪场边界多边形 [[lon, lat], ...]
            
        Returns:
            处理后的雪道列表
        """
        trails = []
        filtered_count = 0
        
        for element in elements:
            trail = self._process_single_trail(element, center_lat, center_lon)
            if trail:
                # 如果有边界，检查雪道是否在边界内
                if boundary:
                    if self._trail_in_boundary(trail['geometry'], boundary):
                        trails.append(trail)
                    else:
                        filtered_count += 1
                else:
                    # 没有边界，使用原有的距离过滤（保留5公里内）
                    if trail['distance_from_center_km'] <= 5.0:
                        trails.append(trail)
                    else:
                        filtered_count += 1
        
        if filtered_count > 0:
            self.log('INFO', f'✓ 过滤掉 {filtered_count} 条雪道，保留 {len(trails)} 条')
        
        return trails
    
    def _trail_in_boundary(self, trail_geometry: List[List[float]], boundary: List[List[float]]) -> bool:
        """
        判断雪道是否在边界内
        采用采样策略：检查雪道上多个点
        
        Args:
            trail_geometry: 雪道几何 [[lon, lat], ...]
            boundary: 边界多边形 [[lon, lat], ...]
            
        Returns:
            True 如果雪道在边界内
        """
        if not trail_geometry or len(trail_geometry) < 2:
            return False
        
        # 采样策略：检查起点、中点、终点和若干中间点
        sample_points = []
        
        # 起点和终点
        sample_points.append(trail_geometry[0])
        sample_points.append(trail_geometry[-1])
        
        # 中点
        mid_idx = len(trail_geometry) // 2
        sample_points.append(trail_geometry[mid_idx])
        
        # 额外的采样点（每隔几个点采样一个）
        step = max(1, len(trail_geometry) // 5)
        for i in range(step, len(trail_geometry), step):
            sample_points.append(trail_geometry[i])
        
        # 如果大部分采样点在边界内，则认为雪道在边界内
        inside_count = sum(1 for point in sample_points if self._point_in_polygon(point, boundary))
        
        # 至少50%的采样点在边界内
        return inside_count >= len(sample_points) * 0.5
    
    def _point_in_polygon(self, point: List[float], polygon: List[List[float]]) -> bool:
        """
        射线法判断点是否在多边形内
        
        Args:
            point: 点 [lon, lat]
            polygon: 多边形 [[lon, lat], ...]
            
        Returns:
            True 如果点在多边形内
        """
        x, y = point[0], point[1]
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
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

