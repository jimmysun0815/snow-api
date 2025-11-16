#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Places API 采集器
用于获取雪场的联系信息（地址、电话、网站等）
"""

import requests
from typing import Optional, Dict
from .base import BaseCollector
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class GooglePlacesCollector(BaseCollector):
    """Google Places API 采集器"""
    
    API_BASE_URL = "https://maps.googleapis.com/maps/api/place"
    
    def __init__(self, resort_config: Dict):
        """
        初始化采集器
        
        Args:
            resort_config: 雪场配置
        """
        super().__init__(resort_config)
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
        
        if not self.api_key:
            self.log('WARNING', 'GOOGLE_MAPS_API_KEY 未设置，将跳过 Google Places API 采集')
    
    def collect(self) -> Optional[Dict]:
        """
        从 Google Places API 采集雪场联系信息
        
        Returns:
            包含联系信息的字典或 None
        """
        if not self.api_key:
            self.log('WARNING', '跳过 Google Places API 采集（未配置 API Key）')
            return None
        
        # 获取雪场的经纬度和名称
        lat = self.resort_config.get('lat')
        lon = self.resort_config.get('lon')
        name = self.resort_config.get('name')
        
        if not lat or not lon or not name:
            self.log('ERROR', '缺少必要信息（lat/lon/name）')
            return None
        
        self.log('INFO', f'开始搜索雪场: {name} ({lat}, {lon})')
        
        # 步骤 1: 使用 Nearby Search 或 Text Search 查找雪场
        place_id = self._find_place(name, lat, lon)
        
        if not place_id:
            self.log('WARNING', f'未找到雪场的 Place ID')
            return None
        
        self.log('INFO', f'找到 Place ID: {place_id}')
        
        # 步骤 2: 使用 Place Details 获取详细信息
        details = self._get_place_details(place_id)
        
        if not details:
            self.log('WARNING', f'无法获取雪场详细信息')
            return None
        
        self.log('INFO', f'成功获取联系信息')
        return details
    
    def _find_place(self, name: str, lat: float, lon: float) -> Optional[str]:
        """
        查找雪场的 Place ID
        
        Args:
            name: 雪场名称
            lat: 纬度
            lon: 经度
            
        Returns:
            Place ID 或 None
        """
        # 使用 Text Search API（更适合按名称搜索）
        from urllib.parse import urlencode
        
        params = {
            'query': f"{name} ski resort",
            'location': f"{lat},{lon}",
            'radius': 5000,  # 5公里范围内
            'key': self.api_key
        }
        
        url = f"{self.API_BASE_URL}/textsearch/json?{urlencode(params)}"
        
        try:
            response = self.fetch_with_retry(url, max_retries=2, timeout=10)
            
            if not response:
                return None
            
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('results'):
                # 返回第一个结果的 place_id
                return data['results'][0].get('place_id')
            else:
                self.log('WARNING', f"Google Places API 返回状态: {data.get('status')}")
                return None
                
        except Exception as e:
            self.log('ERROR', f'查找 Place ID 失败: {str(e)}')
            return None
    
    def _get_place_details(self, place_id: str) -> Optional[Dict]:
        """
        获取雪场的详细信息
        
        Args:
            place_id: Google Place ID
            
        Returns:
            包含联系信息的字典或 None
        """
        from urllib.parse import urlencode
        
        params = {
            'place_id': place_id,
            'fields': 'name,formatted_address,address_components,formatted_phone_number,international_phone_number,website,geometry,rating,user_ratings_total,opening_hours',
            'key': self.api_key
        }
        
        url = f"{self.API_BASE_URL}/details/json?{urlencode(params)}"
        
        try:
            response = self.fetch_with_retry(url, max_retries=2, timeout=10)
            
            if not response:
                return None
            
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('result'):
                result = data['result']
                
                # 解析地址组件
                address_components = result.get('address_components', [])
                street_address = None
                city = None
                state = None
                postal_code = None
                country = None
                
                for component in address_components:
                    types = component.get('types', [])
                    if 'street_number' in types or 'route' in types:
                        if not street_address:
                            street_address = component.get('long_name', '')
                        else:
                            street_address = f"{street_address} {component.get('long_name', '')}"
                    elif 'locality' in types:
                        city = component.get('long_name')
                    elif 'administrative_area_level_1' in types:
                        state = component.get('short_name')
                    elif 'postal_code' in types:
                        postal_code = component.get('long_name')
                    elif 'country' in types:
                        country = component.get('long_name')
                
                # 构建返回数据
                contact_info = {
                    'name': result.get('name'),
                    'formatted_address': result.get('formatted_address'),
                    'street_address': street_address,
                    'city': city,
                    'state': state,
                    'postal_code': postal_code,
                    'country': country,
                    'phone': result.get('formatted_phone_number') or result.get('international_phone_number'),
                    'website': result.get('website'),
                    'rating': result.get('rating'),
                    'user_ratings_total': result.get('user_ratings_total'),
                    'place_id': place_id,
                    # 保留经纬度（可能更准确）
                    'geometry': result.get('geometry', {}).get('location')
                }
                
                return contact_info
            else:
                self.log('WARNING', f"Place Details API 返回状态: {data.get('status')}")
                return None
                
        except Exception as e:
            self.log('ERROR', f'获取详细信息失败: {str(e)}')
            return None

