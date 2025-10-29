#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
展示所有雪场的 Freezing Level 数据
"""

from resort_manager import ResortDataManager


def show_freezing_levels():
    """展示所有雪场的冰冻高度信息"""
    
    manager = ResortDataManager()
    data = manager.load_latest_data()
    
    if not data:
        print("❌ 没有可用数据，请先运行: python collect_data.py")
        return
    
    resorts = data.get('resorts', [])
    
    print("\n" + "=" * 90)
    print("❄️  雪场 Freezing Level（冰冻高度）报告")
    print("=" * 90)
    print()
    print("说明: Freezing Level 表示在哪个海拔高度温度为 0°C")
    print("     - 雪场海拔 > 冰冻高度 = 会下雪 ❄️")
    print("     - 雪场海拔 < 冰冻高度 = 可能下雨 🌧️")
    print()
    print("=" * 90)
    print()
    
    for resort in resorts:
        name = resort.get('name', 'Unknown')
        weather = resort.get('weather', {})
        
        if not weather:
            print(f"📍 {name}")
            print(f"   ⚠️  暂无天气数据")
            print()
            continue
        
        freezing_current = weather.get('freezing_level_current')
        freezing_avg = weather.get('freezing_level_24h_avg')
        today = weather.get('today', {})
        
        print(f"📍 {name}")
        print("-" * 90)
        
        # 冰冻高度
        if freezing_current:
            print(f"   🌡️  当前冰冻高度:     {freezing_current:.0f} 米")
        if freezing_avg:
            print(f"   📊 24小时平均:        {freezing_avg:.0f} 米")
        
        # 今日天气
        if today:
            temp_min = today.get('temp_min')
            temp_max = today.get('temp_max')
            snowfall = today.get('snowfall')
            precipitation = today.get('precipitation')
            
            if temp_min is not None and temp_max is not None:
                print(f"   🌡️  今日温度:         {temp_min}°C ~ {temp_max}°C")
            
            if snowfall is not None:
                if snowfall > 0:
                    print(f"   ❄️  今日降雪:         {snowfall} cm")
                else:
                    print(f"   ❄️  今日降雪:         无")
            
            if precipitation is not None and precipitation > 0:
                print(f"   💧 今日降水:         {precipitation} mm")
        
        # 未来降雪预报
        forecast = weather.get('forecast_7d', [])
        if forecast:
            print()
            print("   📅 未来7天降雪预报:")
            for day in forecast:
                date = day.get('date', 'N/A')
                snowfall = day.get('snowfall', 0)
                temp_min = day.get('temp_min')
                temp_max = day.get('temp_max')
                
                if snowfall and snowfall > 0:
                    emoji = "❄️"
                else:
                    emoji = "  "
                
                temp_str = f"{temp_min}°C~{temp_max}°C" if temp_min and temp_max else "N/A"
                print(f"      {emoji} {date}: {temp_str:15s} 降雪 {snowfall:.1f} cm")
        
        print()
    
    print("=" * 90)
    print(f"数据更新时间: {data.get('metadata', {}).get('timestamp')}")
    print("=" * 90)


if __name__ == '__main__':
    show_freezing_levels()


