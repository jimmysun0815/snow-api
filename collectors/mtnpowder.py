#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MtnPowder API 采集器
用于采集使用 MtnPowder 服务的雪场数据
"""

import requests
from typing import Optional, Dict
from .base import BaseCollector


class MtnPowderCollector(BaseCollector):
    """MtnPowder API 采集器"""
    
    API_BASE_URL = "https://www.mtnpowder.com/feed"
    
    def collect(self) -> Optional[Dict]:
        """
        从 MtnPowder API 采集数据
        
        Returns:
            原始 JSON 数据或 None
        """
        url = f"{self.API_BASE_URL}?resortId={self.source_id}"
        
        self.log('INFO', f'开始采集数据: {url}')
        
        # 添加随机延迟，避免被识别为机器人
        self.random_delay(2.0, 3.0)
        
        # 使用带重试的请求方法
        response = self.fetch_with_retry(url, max_retries=3, timeout=10)
        
        if not response:
            return None
        
        try:
            data = response.json()
            self.log('INFO', f'数据采集成功，大小: {len(response.content)} bytes')
            return data
        except ValueError as e:
            self.log('ERROR', f'JSON 解析失败: {e}')
            return None
        except Exception as e:
            self.log('ERROR', f'未知错误: {str(e)}')
            return None

