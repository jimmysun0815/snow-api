#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控历史记录管理
追踪数据质量趋势
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class MonitorHistory:
    """监控历史记录管理器"""
    
    def __init__(self, history_file: str = 'data/monitor_history.json'):
        """
        初始化历史记录管理器
        
        Args:
            history_file: 历史记录文件路径
        """
        self.history_file = history_file
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] 加载历史记录失败: {e}")
            return []
    
    def add_record(self, report_data: Dict):
        """
        添加监控记录
        
        Args:
            report_data: 监控报告数据（来自 monitor_report.json）
        """
        # 提取摘要信息
        timestamp = report_data.get('timestamp', datetime.now().isoformat())
        summary = report_data.get('summary', {})
        
        # 创建历史记录条目
        record = {
            'timestamp': timestamp,
            'total': summary.get('total', 0),
            'success': summary.get('success', 0),
            'warning': summary.get('warning', 0),
            'error': summary.get('error', 0),
            'avg_score': summary.get('avg_score', 0),
            'resorts': {}
        }
        
        # 记录每个雪场的分数
        for resort in report_data.get('resorts', []):
            resort_id = resort.get('resort_id')
            if resort_id:
                record['resorts'][str(resort_id)] = {
                    'name': resort.get('resort_name'),
                    'status': resort.get('overall_status'),
                    'score': resort.get('score'),
                    'data_source': resort.get('data_source')
                }
        
        # 添加到历史记录
        self.history.append(record)
        
        # 保持最近 100 条记录
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        # 保存
        self._save_history()
    
    def _save_history(self):
        """保存历史记录"""
        Path(self.history_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def get_trend_data(self, resort_id: Optional[int] = None, days: int = 7) -> Dict:
        """
        获取趋势数据
        
        Args:
            resort_id: 雪场 ID（None 表示所有雪场）
            days: 最近 N 天
            
        Returns:
            趋势数据字典
        """
        if not self.history:
            return {'labels': [], 'data': []}
        
        # 过滤最近 N 天的记录
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        recent_records = []
        
        for record in self.history:
            try:
                record_time = datetime.fromisoformat(record['timestamp']).timestamp()
                if record_time >= cutoff_time:
                    recent_records.append(record)
            except:
                continue
        
        if not recent_records:
            return {'labels': [], 'data': []}
        
        # 如果是特定雪场
        if resort_id is not None:
            labels = []
            scores = []
            
            for record in recent_records:
                resort_data = record['resorts'].get(str(resort_id))
                if resort_data:
                    try:
                        dt = datetime.fromisoformat(record['timestamp'])
                        labels.append(dt.strftime('%m/%d %H:%M'))
                        scores.append(resort_data['score'])
                    except:
                        continue
            
            return {
                'labels': labels,
                'data': scores,
                'type': 'resort',
                'resort_id': resort_id
            }
        
        # 所有雪场的汇总趋势
        else:
            labels = []
            avg_scores = []
            success_rates = []
            
            for record in recent_records:
                try:
                    dt = datetime.fromisoformat(record['timestamp'])
                    labels.append(dt.strftime('%m/%d %H:%M'))
                    avg_scores.append(record['avg_score'])
                    
                    total = record['total']
                    if total > 0:
                        success_rate = (record['success'] / total) * 100
                        success_rates.append(success_rate)
                    else:
                        success_rates.append(0)
                except:
                    continue
            
            return {
                'labels': labels,
                'avg_scores': avg_scores,
                'success_rates': success_rates,
                'type': 'overall'
            }
    
    def get_problem_resorts_trend(self, days: int = 7) -> List[Dict]:
        """
        获取经常出问题的雪场列表
        
        Args:
            days: 最近 N 天
            
        Returns:
            问题雪场列表，按问题频率排序
        """
        if not self.history:
            return []
        
        # 统计每个雪场的问题出现次数
        resort_issues = {}
        
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        
        for record in self.history:
            try:
                record_time = datetime.fromisoformat(record['timestamp']).timestamp()
                if record_time < cutoff_time:
                    continue
            except:
                continue
            
            for resort_id, resort_data in record['resorts'].items():
                if resort_id not in resort_issues:
                    resort_issues[resort_id] = {
                        'resort_id': int(resort_id),
                        'name': resort_data['name'],
                        'data_source': resort_data['data_source'],
                        'total_checks': 0,
                        'error_count': 0,
                        'warning_count': 0,
                        'avg_score': []
                    }
                
                resort_issues[resort_id]['total_checks'] += 1
                resort_issues[resort_id]['avg_score'].append(resort_data['score'])
                
                if resort_data['status'] == 'error':
                    resort_issues[resort_id]['error_count'] += 1
                elif resort_data['status'] == 'warning':
                    resort_issues[resort_id]['warning_count'] += 1
        
        # 计算平均分数和问题率
        result = []
        for resort_id, data in resort_issues.items():
            if data['total_checks'] > 0:
                data['avg_score'] = sum(data['avg_score']) / len(data['avg_score'])
                data['error_rate'] = (data['error_count'] / data['total_checks']) * 100
                data['warning_rate'] = (data['warning_count'] / data['total_checks']) * 100
                result.append(data)
        
        # 按错误率排序
        result.sort(key=lambda x: (x['error_rate'], x['warning_rate']), reverse=True)
        
        return result
    
    def generate_summary_report(self, days: int = 7) -> str:
        """
        生成文本摘要报告
        
        Args:
            days: 最近 N 天
            
        Returns:
            文本报告
        """
        trend_data = self.get_trend_data(days=days)
        problem_resorts = self.get_problem_resorts_trend(days=days)
        
        report = []
        report.append("\n" + "=" * 70)
        report.append(f"📈 数据质量趋势分析（最近 {days} 天）")
        report.append("=" * 70)
        
        if trend_data['labels']:
            report.append(f"\n记录数: {len(trend_data['labels'])} 次采集")
            
            avg_scores = trend_data.get('avg_scores', [])
            if avg_scores:
                current_score = avg_scores[-1]
                avg_score = sum(avg_scores) / len(avg_scores)
                
                report.append(f"当前平均分数: {current_score:.1f}%")
                report.append(f"期间平均分数: {avg_score:.1f}%")
                
                # 趋势判断
                if len(avg_scores) >= 2:
                    trend = avg_scores[-1] - avg_scores[0]
                    if trend > 5:
                        report.append(f"趋势: 📈 改善 (+{trend:.1f}%)")
                    elif trend < -5:
                        report.append(f"趋势: 📉 下降 ({trend:.1f}%)")
                    else:
                        report.append(f"趋势: ➡️  稳定")
        else:
            report.append("\n暂无历史数据")
        
        # 问题雪场
        if problem_resorts:
            report.append("\n" + "-" * 70)
            report.append("⚠️  需要重点关注的雪场:")
            report.append("-" * 70)
            
            for i, resort in enumerate(problem_resorts[:10], 1):
                if resort['error_rate'] > 0 or resort['warning_rate'] > 50:
                    icon = '❌' if resort['error_rate'] > 0 else '⚠️'
                    report.append(
                        f"{i}. {icon} {resort['name']} (ID: {resort['resort_id']})\n"
                        f"   数据源: {resort['data_source']} | "
                        f"平均分数: {resort['avg_score']:.1f}% | "
                        f"错误率: {resort['error_rate']:.1f}% | "
                        f"警告率: {resort['warning_rate']:.1f}%"
                    )
        
        report.append("=" * 70 + "\n")
        
        return "\n".join(report)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='监控历史记录管理')
    parser.add_argument(
        '--add',
        help='添加监控记录（从 JSON 报告文件）'
    )
    parser.add_argument(
        '--trend',
        action='store_true',
        help='显示趋势分析'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='分析天数（默认 7 天）'
    )
    parser.add_argument(
        '--resort-id',
        type=int,
        help='特定雪场 ID 的趋势'
    )
    
    args = parser.parse_args()
    
    history = MonitorHistory()
    
    # 添加记录
    if args.add:
        try:
            with open(args.add, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            history.add_record(report_data)
            print(f"[OK] 已添加监控记录到历史")
        except Exception as e:
            print(f"[ERROR] 添加记录失败: {e}")
        return
    
    # 显示趋势
    if args.trend:
        print(history.generate_summary_report(days=args.days))
        return
    
    # 默认：显示历史记录统计
    print(f"\n历史记录统计:")
    print(f"  总记录数: {len(history.history)}")
    
    if history.history:
        first_record = history.history[0]
        last_record = history.history[-1]
        
        try:
            first_time = datetime.fromisoformat(first_record['timestamp'])
            last_time = datetime.fromisoformat(last_record['timestamp'])
            
            print(f"  最早记录: {first_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  最新记录: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass


if __name__ == '__main__':
    main()

