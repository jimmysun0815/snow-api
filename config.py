#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Configuration Management - Loads config from environment variables

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Config:
    """应用配置"""
    
    # PostgreSQL 配置
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5433))
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'app')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'app')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'snow')
    
    # 数据库连接 URL
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'
    )
    
    # Redis 配置
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6380))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_URL = os.getenv(
        'REDIS_URL',
        f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    )
    
    # 缓存配置
    CACHE_TTL = int(os.getenv('CACHE_TTL', 300))  # 5分钟
    
    # 数据采集配置
    DATA_COLLECTION_INTERVAL = int(os.getenv('DATA_COLLECTION_INTERVAL', 3600))  # 1小时
    
    # Open-Meteo API 配置
    OPENMETEO_API_KEY = os.getenv('OPENMETEO_API_KEY', '')  # 付费 API Key（可选）

    # NewsData.io 新闻 API（用于美加滑雪场相关新闻）
    NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY', '')
    
    @classmethod
    def display(cls):
        """显示当前配置"""
        print("=" * 80)
        print("📋 当前配置")
        print("=" * 80)
        print(f"PostgreSQL: {cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}")
        print(f"Redis: {cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}")
        print(f"缓存 TTL: {cls.CACHE_TTL} 秒")
        print(f"采集间隔: {cls.DATA_COLLECTION_INTERVAL} 秒")
        print(f"Open-Meteo API Key: {'已设置' if cls.OPENMETEO_API_KEY else '未设置（使用免费版）'}")
        print(f"NewsData.io API Key: {'已设置' if cls.NEWSDATA_API_KEY else '未设置'}")
        print("=" * 80)


