#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OnTheSnow 网页采集器
通过抓取网页中的 __NEXT_DATA__ JSON 数据
"""

import requests
import re
import json
from typing import Optional, Dict
from .base import BaseCollector


class OnTheSnowCollector(BaseCollector):
    """OnTheSnow 网页采集器"""
    
    def collect(self) -> Optional[Dict]:
        """
        从 OnTheSnow 网页采集数据
        
        Returns:
            原始 JSON 数据或 None
        """
        url = self.resort_config.get('source_url')
        
        if not url:
            self.log('ERROR', '缺少 source_url 配置')
            return None
        
        self.log('INFO', f'开始采集数据: {url}')
        
        # 添加小延迟，避免被识别为机器人（并发模式下保持较短延迟）
        self.random_delay(0.5, 1.0)
        
        # 使用带重试的请求方法
        response = self.fetch_with_retry(url, max_retries=3, timeout=15)
        
        if not response:
            return None
        
        try:
            # 查找 __NEXT_DATA__ JSON
            match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                response.text,
                re.DOTALL
            )
            
            if match:
                try:
                    data = json.loads(match.group(1))
                    self.log('INFO', f'数据采集成功，找到 __NEXT_DATA__')
                    return data
                except json.JSONDecodeError as e:
                    self.log('ERROR', f'JSON 解析失败: {e}')
                    return None
            else:
                self.log('ERROR', '未找到 __NEXT_DATA__')
                return None
                
        except Exception as e:
            self.log('ERROR', f'未知错误: {str(e)}')
            return None

