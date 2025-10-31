#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型定义
使用 SQLAlchemy ORM
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()


class Resort(Base):
    """雪场基本信息表"""
    __tablename__ = 'resorts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    location = Column(String(200))
    lat = Column(Float)
    lon = Column(Float)
    elevation_min = Column(Integer)
    elevation_max = Column(Integer)
    boundary = Column(JSON)  # 雪场边界多边形坐标 [[lon, lat], ...]
    data_source = Column(String(50))
    source_url = Column(Text)
    source_id = Column(String(100))
    enabled = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关联关系
    conditions = relationship("ResortCondition", back_populates="resort", cascade="all, delete-orphan")
    weather = relationship("ResortWeather", back_populates="resort", cascade="all, delete-orphan")
    trails = relationship("ResortTrail", back_populates="resort", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Resort(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class ResortCondition(Base):
    """雪场雪况数据表（时序数据）"""
    __tablename__ = 'resort_conditions'
    
    id = Column(Integer, primary_key=True)
    resort_id = Column(Integer, ForeignKey('resorts.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)
    
    # 状态
    status = Column(String(20))  # open, closed, partial
    
    # 雪况
    new_snow = Column(Float, default=0)  # 24h新雪 (cm)
    base_depth = Column(Float, default=0)  # 雪底深度 (cm)
    
    # 设施
    lifts_open = Column(Integer, default=0)
    lifts_total = Column(Integer, default=0)
    trails_open = Column(Integer, default=0)
    trails_total = Column(Integer, default=0)
    
    # 天气
    temperature = Column(Float)  # 温度 (°C)
    
    # 额外数据 (JSON)
    extra_data = Column(JSON)
    
    # 元数据
    source = Column(Text)
    data_source = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    resort = relationship("Resort", back_populates="conditions")
    
    def __repr__(self):
        return f"<ResortCondition(resort_id={self.resort_id}, timestamp={self.timestamp}, status='{self.status}')>"


class ResortWeather(Base):
    """雪场天气数据表（时序数据）"""
    __tablename__ = 'resort_weather'
    
    id = Column(Integer, primary_key=True)
    resort_id = Column(Integer, ForeignKey('resorts.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)
    
    # 当前天气
    current_temp = Column(Float)
    current_humidity = Column(Integer)
    current_windspeed = Column(Float)
    current_winddirection = Column(Float)
    current_winddirection_compass = Column(String(10))
    
    # 冰冻线
    freezing_level_current = Column(Float)
    freezing_level_24h_avg = Column(Float)
    
    # 今日数据
    today_sunrise = Column(String(50))
    today_sunset = Column(String(50))
    today_temp_max = Column(Float)
    today_temp_min = Column(Float)
    
    # 按海拔的温度数据
    temp_base = Column(Float)      # 山脚温度
    temp_mid = Column(Float)       # 山腰温度
    temp_summit = Column(Float)    # 山顶温度
    
    # 预报数据 (JSON)
    hourly_forecast = Column(JSON)  # 24小时预报（包含分层温度）
    forecast_7d = Column(JSON)  # 7天预报
    
    # 元数据
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    resort = relationship("Resort", back_populates="weather")
    
    def __repr__(self):
        return f"<ResortWeather(resort_id={self.resort_id}, timestamp={self.timestamp})>"


class ResortTrail(Base):
    """雪场雪道数据表"""
    __tablename__ = 'resort_trails'
    
    id = Column(Integer, primary_key=True)
    resort_id = Column(Integer, ForeignKey('resorts.id'), nullable=False, index=True)
    
    # OSM 数据
    osm_id = Column(String(50), index=True)
    osm_type = Column(String(20))  # way/relation
    
    # 雪道信息
    name = Column(String(200))
    difficulty = Column(String(50), index=True)  # novice/easy/intermediate/advanced/expert/freeride
    piste_type = Column(String(50))  # downhill/nordic/skitour
    
    # 几何数据
    geometry = Column(JSON)  # GeoJSON 格式的坐标
    length_meters = Column(Float)
    
    # 额外属性
    lit = Column(Boolean)  # 是否有夜间照明
    grooming = Column(String(50))  # 压雪情况
    width = Column(String(50))  # 宽度
    ref = Column(String(50))  # 编号
    
    # 元数据
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联关系
    resort = relationship("Resort", back_populates="trails")
    
    def __repr__(self):
        return f"<ResortTrail(resort_id={self.resort_id}, name='{self.name}', difficulty='{self.difficulty}')>"


# 数据库初始化函数
def init_db(database_url):
    """
    初始化数据库
    
    Args:
        database_url: 数据库连接字符串
    """
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """
    获取数据库会话
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        Session 对象
    """
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    # 测试创建表
    from config import Config
    
    print("=" * 80)
    print("🗄️  数据库初始化")
    print("=" * 80)
    print(f"连接: {Config.DATABASE_URL}")
    print()
    
    try:
        engine = init_db(Config.DATABASE_URL)
        print("✅ 数据库表创建成功!")
        print()
        print("创建的表:")
        for table in Base.metadata.tables:
            print(f"  • {table}")
        print()
        print("=" * 80)
    except Exception as e:
        print(f"❌ 错误: {e}")
        print("=" * 80)

