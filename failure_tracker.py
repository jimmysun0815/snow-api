#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据采集失败追踪器
记录采集过程中的404和其他错误
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class CollectionFailureTracker:
    """采集失败追踪器"""
    
    def __init__(self, output_file: str = 'data/collection_failures.json'):
        """初始化追踪器"""
        self.output_file = output_file
        self.failures: List[Dict] = []
    
    def add_failure(self, resort_id: int, resort_name: str, error_type: str, 
                   error_message: str, url: str = None):
        """
        记录一个失败
        
        Args:
            resort_id: 雪场ID
            resort_name: 雪场名称
            error_type: 错误类型 (HTTP_404, TIMEOUT, JSON_ERROR等)
            error_message: 错误信息
            url: 请求的URL
        """
        self.failures.append({
            'resort_id': resort_id,
            'resort_name': resort_name,
            'error_type': error_type,
            'error_message': error_message,
            'url': url,
            'timestamp': datetime.now().isoformat()
        })
    
    def save(self):
        """保存失败记录到文件"""
        Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_failures': len(self.failures),
            'failures': self.failures
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def print_summary(self):
        """打印失败摘要"""
        if not self.failures:
            print("✅ 所有雪场采集成功")
            return
        
        print(f"\n❌ 发现 {len(self.failures)} 个采集失败:")
        print("=" * 70)
        
        # 按错误类型分组
        error_groups = {}
        for f in self.failures:
            error_type = f['error_type']
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(f)
        
        for error_type, failures in error_groups.items():
            print(f"\n{error_type}: {len(failures)} 个")
            for f in failures[:10]:  # 只显示前10个
                print(f"  • {f['resort_name']} ({f['resort_id']})")
                if f['url']:
                    print(f"    URL: {f['url']}")
                print(f"    原因: {f['error_message']}")
        
        print("\n" + "=" * 70)
        print(f"详细信息已保存到: {self.output_file}")

