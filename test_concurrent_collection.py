#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试并发采集速度
"""

import time
from resort_manager import ResortDataManager
from datetime import datetime

def main():
    print("=" * 70)
    print("🚀 测试并发采集")
    print("=" * 70)
    print()
    
    # 初始化管理器（不连接数据库，只测试采集速度）
    manager = ResortDataManager(use_db=False)
    
    # 获取启用的雪场数量
    enabled_resorts = [r for r in manager.resorts if r.get('enabled', False)]
    total_count = len(enabled_resorts)
    
    print(f"📊 总共 {total_count} 个启用的雪场")
    print()
    
    # 测试采集前 20 个雪场
    test_count = min(20, total_count)
    print(f"🧪 测试采集前 {test_count} 个雪场...")
    print()
    
    # 临时修改配置，只采集前 N 个
    manager.resorts = enabled_resorts[:test_count]
    
    # 开始计时
    start_time = time.time()
    start_datetime = datetime.now()
    
    # 执行采集
    results = manager.collect_all(enabled_only=False, max_workers=20)
    
    # 结束计时
    end_time = time.time()
    end_datetime = datetime.now()
    duration = end_time - start_time
    
    # 显示结果
    print()
    print("=" * 70)
    print("📊 采集结果统计")
    print("=" * 70)
    print(f"⏱️  总耗时: {duration:.2f} 秒")
    print(f"✅ 成功: {len(results)}/{test_count}")
    print(f"❌ 失败: {test_count - len(results)}/{test_count}")
    print(f"📈 平均每个雪场: {duration / test_count:.2f} 秒")
    print()
    
    # 估算全部采集时间
    if test_count > 0:
        estimated_full_time = (duration / test_count) * total_count
        print(f"🔮 估算采集全部 {total_count} 个雪场需要: {estimated_full_time / 60:.1f} 分钟")
        print()
    
    # 如果时间超过 14 分钟，给出警告
    estimated_full_minutes = estimated_full_time / 60 if test_count > 0 else 0
    if estimated_full_minutes > 14:
        print("⚠️  警告: 估算时间超过 Lambda 最大超时（15分钟）")
        print(f"   建议增加并发线程数或分批采集")
        print()
    else:
        print("✅ 估算时间在 Lambda 超时限制内，可以全量采集")
        print()
    
    print("提示: 设置 OPENMETEO_API_KEY 环境变量可以使用付费 API（无速率限制）")
    print()

if __name__ == '__main__':
    main()

