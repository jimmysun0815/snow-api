#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集器模块
"""

from .base import BaseCollector
from .mtnpowder import MtnPowderCollector
from .onthesnow import OnTheSnowCollector
from .openmeteo import OpenMeteoCollector
from .osm_trails import OSMTrailsCollector

__all__ = ['BaseCollector', 'MtnPowderCollector', 'OnTheSnowCollector', 'OpenMeteoCollector', 'OSMTrailsCollector']

