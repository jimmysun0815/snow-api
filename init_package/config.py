#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理
从环境变量或默认值加载配置
"""

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
        print("=" * 80)


