#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集器基类
定义所有采集器的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime
import requests
import time
import random


class BaseCollector(ABC):
    """采集器基类"""
    
    def __init__(self, resort_config: Dict):
        """
        初始化采集器
        
        Args:
            resort_config: 雪场配置信息
        """
        self.resort_config = resort_config
        self.resort_id = resort_config.get('id')
        self.resort_name = resort_config.get('name')
        self.source_id = resort_config.get('source_id')
        
    @abstractmethod
    def collect(self) -> Optional[Dict]:
        """
        采集数据
        
        Returns:
            原始数据字典，如果采集失败返回 None
        """
        pass
    
    def get_headers(self) -> Dict:
        """
        获取 HTTP 请求头
        
        Returns:
            请求头字典
        """
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    
    def log(self, level: str, message: str):
        """
        记录日志
        
        Args:
            level: 日志级别 (INFO, WARNING, ERROR)
            message: 日志消息
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] [{self.resort_name}] {message}")
    
    def random_delay(self, min_seconds: float = 0.5, max_seconds: float = 1.0):
        """
        随机延迟（并发模式下使用较短延迟）
        
        Args:
            min_seconds: 最小延迟秒数
            max_seconds: 最大延迟秒数
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def fetch_with_retry(self, url: str, max_retries: int = 3, timeout: int = 10) -> Optional[requests.Response]:
        """
        带重试机制的 HTTP 请求
        
        Args:
            url: 请求 URL
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            
        Returns:
            Response 对象，失败返回 None
        """
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=self.get_headers(),
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 404:
                    self.log('ERROR', f'HTTP 404')
                    return None
                else:
                    self.log('WARNING', f'HTTP {response.status_code}, 尝试 {attempt + 1}/{max_retries}')
                    
            except requests.exceptions.Timeout:
                self.log('WARNING', f'请求超时, 尝试 {attempt + 1}/{max_retries}')
            except requests.exceptions.ConnectionError:
                self.log('WARNING', f'连接错误, 尝试 {attempt + 1}/{max_retries}')
            except requests.exceptions.RequestException as e:
                self.log('WARNING', f'请求失败: {str(e)[:50]}, 尝试 {attempt + 1}/{max_retries}')
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 递增等待时间：2s, 4s, 6s
                self.log('INFO', f'等待 {wait_time} 秒后重试...')
                time.sleep(wait_time)
        
        self.log('ERROR', f'达到最大重试次数 ({max_retries}), 采集失败')
        return None

