#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪场数据监控器
分析数据质量并生成监控报告
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class FieldCheck:
    """字段检查结果"""
    field_name: str
    status: str  # 'success', 'warning', 'error'
    value: any
    message: str


@dataclass
class ResortMonitorReport:
    """雪场监控报告"""
    resort_id: int
    resort_name: str
    overall_status: str  # 'success', 'warning', 'error'
    data_source: str
    last_update: str
    checks: List[FieldCheck]
    score: float  # 数据完整度分数 0-100


class DataMonitor:
    """数据质量监控器"""
    
    # 定义需要检查的字段及其重要性
    CRITICAL_FIELDS = {
        'name': '雪场名称',
        'status': '开放状态',
        'data_source': '数据来源',
    }
    
    SNOW_FIELDS = {
        'new_snow': '24h新雪',
        'base_depth': '雪底深度',
        'lifts_open': '开放缆车',
        'lifts_total': '总缆车数',
        'trails_open': '开放雪道',
        'trails_total': '总雪道数',
    }
    
    WEATHER_FIELDS = {
        'weather.current.temperature': '当前温度',
        'weather.current.humidity': '湿度',
        'weather.current.windspeed': '风速',
        'weather.freezing_level_current': '当前冰冻线',
        'weather.temp_base': '山脚温度',
        'weather.temp_summit': '山顶温度',
    }
    
    OPTIONAL_FIELDS = {
        'weather.hourly_forecast': '24小时预报',
        'weather.forecast_7d': '7天预报',
        'elevation': '海拔信息',
    }
    
    def __init__(self):
        """初始化监控器"""
        self.reports: List[ResortMonitorReport] = []
    
    def _get_nested_value(self, data: Dict, key: str) -> any:
        """获取嵌套字典的值"""
        keys = key.split('.')
        value = data
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return None
    
    def _check_field(self, data: Dict, field_key: str, field_name: str, is_critical: bool = False) -> FieldCheck:
        """
        检查单个字段
        
        Args:
            data: 雪场数据
            field_key: 字段键（支持嵌套，如 'weather.current.temperature'）
            field_name: 字段名称（中文）
            is_critical: 是否为关键字段
            
        Returns:
            FieldCheck 对象
        """
        value = self._get_nested_value(data, field_key)
        
        # 检查字段是否存在
        if value is None:
            status = 'error' if is_critical else 'warning'
            message = '数据缺失' if is_critical else '暂无数据'
            return FieldCheck(field_name, status, None, message)
        
        # 获取雪场状态
        resort_status = data.get('status', '')
        
        # 检查数值类型字段
        if isinstance(value, (int, float)):
            # 特殊处理：雪场未开放时，雪况数据为 0 是正常的
            if resort_status in ['closed', 'partial']:
                if field_key in ['new_snow', 'base_depth', 'lifts_open', 'trails_open']:
                    if value == 0:
                        return FieldCheck(field_name, 'success', value, '雪场未开放（正常）')
            
            # 温度字段允许负数（冬天常见）
            if 'temperature' in field_key.lower() or 'temp' in field_key.lower():
                # 温度合理范围：-40°C 到 40°C
                if -40 <= value <= 40:
                    return FieldCheck(field_name, 'success', value, '数据正常')
                else:
                    return FieldCheck(field_name, 'error', value, '温度超出合理范围')
            
            # 一般数值字段检查
            if value == 0:
                return FieldCheck(field_name, 'warning', value, '数值为 0')
            elif value < 0:
                return FieldCheck(field_name, 'error', value, '数值异常（负数）')
            else:
                return FieldCheck(field_name, 'success', value, '数据正常')
        
        # 检查字符串类型字段
        elif isinstance(value, str):
            if value.strip() == '':
                return FieldCheck(field_name, 'error', value, '数据为空')
            else:
                return FieldCheck(field_name, 'success', value, '数据正常')
        
        # 检查列表/对象类型字段
        elif isinstance(value, (list, dict)):
            if len(value) == 0:
                return FieldCheck(field_name, 'warning', value, '数据为空')
            else:
                length = len(value)
                return FieldCheck(field_name, 'success', f'{length} 项', '数据正常')
        
        # 其他类型
        else:
            return FieldCheck(field_name, 'success', str(value), '数据正常')
    
    def monitor_resort(self, resort_data: Dict) -> ResortMonitorReport:
        """
        监控单个雪场数据
        
        Args:
            resort_data: 雪场数据
            
        Returns:
            ResortMonitorReport 对象
        """
        checks = []
        error_count = 0
        warning_count = 0
        
        # 1. 检查关键字段
        for field_key, field_name in self.CRITICAL_FIELDS.items():
            check = self._check_field(resort_data, field_key, field_name, is_critical=True)
            checks.append(check)
            if check.status == 'error':
                error_count += 1
            elif check.status == 'warning':
                warning_count += 1
        
        # 2. 检查雪况字段
        for field_key, field_name in self.SNOW_FIELDS.items():
            check = self._check_field(resort_data, field_key, field_name)
            checks.append(check)
            if check.status == 'error':
                error_count += 1
            elif check.status == 'warning':
                warning_count += 1
        
        # 3. 检查天气字段
        for field_key, field_name in self.WEATHER_FIELDS.items():
            check = self._check_field(resort_data, field_key, field_name)
            checks.append(check)
            if check.status == 'error':
                error_count += 1
            elif check.status == 'warning':
                warning_count += 1
        
        # 4. 检查可选字段
        for field_key, field_name in self.OPTIONAL_FIELDS.items():
            check = self._check_field(resort_data, field_key, field_name)
            checks.append(check)
            if check.status == 'warning':
                # 可选字段的警告不计入总数
                pass
        
        # 计算总体状态
        total_checks = len(self.CRITICAL_FIELDS) + len(self.SNOW_FIELDS) + len(self.WEATHER_FIELDS)
        success_count = total_checks - error_count - warning_count
        
        if error_count > 0:
            overall_status = 'error'
        elif warning_count >= total_checks * 0.3:  # 警告超过30%
            overall_status = 'warning'
        else:
            overall_status = 'success'
        
        # 计算数据完整度分数（0-100）
        score = (success_count / total_checks) * 100
        
        # 创建报告
        report = ResortMonitorReport(
            resort_id=resort_data.get('resort_id', 0),
            resort_name=resort_data.get('name', 'Unknown'),
            overall_status=overall_status,
            data_source=resort_data.get('data_source', 'Unknown'),
            last_update=resort_data.get('last_update', 'Unknown'),
            checks=checks,
            score=round(score, 1)
        )
        
        return report
    
    def monitor_all(self, data_file: str = 'data/latest.json') -> List[ResortMonitorReport]:
        """
        监控所有雪场数据
        
        Args:
            data_file: 数据文件路径
            
        Returns:
            监控报告列表
        """
        # 加载数据
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"[ERROR] 数据文件不存在: {data_file}")
            return []
        except json.JSONDecodeError as e:
            print(f"[ERROR] 数据文件解析失败: {e}")
            return []
        
        resorts = data.get('resorts', [])
        
        if not resorts:
            print("[WARNING] 没有找到雪场数据")
            return []
        
        # 监控每个雪场
        self.reports = []
        for resort_data in resorts:
            report = self.monitor_resort(resort_data)
            self.reports.append(report)
        
        return self.reports
    
    def generate_summary(self) -> Dict:
        """
        生成监控摘要
        
        Returns:
            摘要字典
        """
        if not self.reports:
            return {
                'total': 0,
                'success': 0,
                'warning': 0,
                'error': 0,
                'avg_score': 0
            }
        
        total = len(self.reports)
        success = sum(1 for r in self.reports if r.overall_status == 'success')
        warning = sum(1 for r in self.reports if r.overall_status == 'warning')
        error = sum(1 for r in self.reports if r.overall_status == 'error')
        avg_score = sum(r.score for r in self.reports) / total
        
        return {
            'total': total,
            'success': success,
            'warning': warning,
            'error': error,
            'avg_score': round(avg_score, 1)
        }
    
    def save_report(self, output_file: str = 'data/monitor_report.json'):
        """
        保存监控报告为 JSON
        
        Args:
            output_file: 输出文件路径
        """
        summary = self.generate_summary()
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'resorts': [
                {
                    'resort_id': r.resort_id,
                    'resort_name': r.resort_name,
                    'overall_status': r.overall_status,
                    'data_source': r.data_source,
                    'last_update': r.last_update,
                    'score': r.score,
                    'checks': [
                        {
                            'field': c.field_name,
                            'status': c.status,
                            'value': str(c.value) if c.value is not None else None,
                            'message': c.message
                        }
                        for c in r.checks
                    ]
                }
                for r in self.reports
            ]
        }
        
        # 确保目录存在
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] 监控报告已保存: {output_file}")
    
    def print_summary(self):
        """打印监控摘要到控制台"""
        summary = self.generate_summary()
        
        print("\n" + "=" * 70)
        print("📊 数据质量监控摘要")
        print("=" * 70)
        print(f"总雪场数: {summary['total']}")
        print(f"✅ 数据完整: {summary['success']} ({summary['success']/summary['total']*100:.1f}%)")
        print(f"⚠️  数据不完整: {summary['warning']} ({summary['warning']/summary['total']*100:.1f}%)")
        print(f"❌ 数据错误: {summary['error']} ({summary['error']/summary['total']*100:.1f}%)")
        print(f"📈 平均数据完整度: {summary['avg_score']:.1f}%")
        print("=" * 70)
        
        # 打印有问题的雪场
        problem_resorts = [r for r in self.reports if r.overall_status != 'success']
        
        if problem_resorts:
            print("\n⚠️  需要关注的雪场:")
            print("-" * 70)
            for resort in sorted(problem_resorts, key=lambda r: r.score):
                status_icon = '❌' if resort.overall_status == 'error' else '⚠️'
                print(f"{status_icon} {resort.resort_name} (ID: {resort.resort_id})")
                print(f"   数据完整度: {resort.score:.1f}% | 数据源: {resort.data_source}")
                
                # 打印问题字段
                problem_checks = [c for c in resort.checks if c.status in ['error', 'warning']]
                if problem_checks:
                    for check in problem_checks[:5]:  # 只显示前5个问题
                        icon = '❌' if check.status == 'error' else '⚠️'
                        print(f"   {icon} {check.field_name}: {check.message}")
                print()
        else:
            print("\n✅ 所有雪场数据质量良好！")
        
        print("=" * 70 + "\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='雪场数据质量监控工具')
    parser.add_argument(
        '--data-file',
        default='data/latest.json',
        help='数据文件路径'
    )
    parser.add_argument(
        '--output',
        default='data/monitor_report.json',
        help='监控报告输出路径'
    )
    parser.add_argument(
        '--html',
        action='store_true',
        help='生成 HTML 报告'
    )
    
    args = parser.parse_args()
    
    # 创建监控器
    monitor = DataMonitor()
    
    # 执行监控
    print("\n🔍 开始分析数据质量...")
    reports = monitor.monitor_all(args.data_file)
    
    if not reports:
        print("[ERROR] 没有生成监控报告")
        return
    
    # 打印摘要
    monitor.print_summary()
    
    # 保存 JSON 报告
    monitor.save_report(args.output)
    
    # 生成 HTML 报告
    if args.html:
        from monitor_html import generate_html_report
        html_file = args.output.replace('.json', '.html')
        generate_html_report(args.output, html_file)


if __name__ == '__main__':
    main()

