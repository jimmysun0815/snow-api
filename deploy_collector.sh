#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📦 部署 Collector Lambda"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$(dirname "$0")"

# 1. 创建临时目录
echo "🔨 准备部署包..."
rm -rf collector_package
mkdir -p collector_package

# 2. 使用 Docker 安装 Lambda 兼容的依赖
echo "📦 安装依赖 (Lambda 兼容版本)..."
docker run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  --entrypoint /bin/bash \
  public.ecr.aws/sam/build-python3.11:latest \
  -c "pip install -r requirements.txt -t collector_package/"

# 3. 复制应用代码
echo "📄 复制应用代码..."
cp -r collectors collector_package/
cp config.py collector_package/
cp models.py collector_package/
cp db_manager.py collector_package/
cp normalizer.py collector_package/
cp resort_manager.py collector_package/
cp failure_tracker.py collector_package/
cp collect_data.py collector_package/
cp resorts_config.json collector_package/
cp collection_report_generator.py collector_package/

# 4. 创建 Lambda handler
echo "📝 创建 Lambda handler..."
cat > collector_package/collector_handler.py << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda 函数 - 雪场数据采集
"""

import json
import sys
import os
from datetime import datetime

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resort_manager import ResortDataManager
from failure_tracker import CollectionFailureTracker
from collection_report_generator import CollectionReportGenerator

def lambda_handler(event, context):
    """Lambda 处理函数"""
    
    print(f"收到事件: {json.dumps(event)}")
    
    # 记录开始时间
    start_time = datetime.now()
    
    # 从事件中获取参数
    limit = event.get('limit')
    resort_id = event.get('resort_id')
    
    # 初始化报告生成器
    report_generator = CollectionReportGenerator()
    
    try:
        # 初始化管理器
        manager = ResortDataManager(config_file='resorts_config.json')
        failure_tracker = CollectionFailureTracker()
        
        # 单个雪场采集
        if resort_id:
            resort_config = None
            for r in manager.resorts:
                if r.get('id') == resort_id:
                    resort_config = r
                    break
            
            if not resort_config:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': f'Resort ID {resort_id} not found'})
                }
            
            print(f"采集单个雪场: {resort_config.get('name')}")
            data = manager.collect_resort_data(resort_config)
            
            if data:
                manager.save_data([data])
                
                # 生成报告
                end_time = datetime.now()
                stats = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'total_resorts': 1,
                    'success_count': 1,
                    'fail_count': 0,
                    'failed_resorts': [],
                    'data_quality': {}
                }
                generate_and_upload_report(report_generator, stats)
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Data collected successfully',
                        'resort': resort_config.get('name')
                    })
                }
            else:
                # 生成失败报告
                end_time = datetime.now()
                stats = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'total_resorts': 1,
                    'success_count': 0,
                    'fail_count': 1,
                    'failed_resorts': [{'name': resort_config.get('name'), 'error': 'Collection failed'}],
                    'data_quality': {}
                }
                generate_and_upload_report(report_generator, stats)
                
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Collection failed'})
                }
        
        # 批量采集
        resorts_to_collect = [
            r for r in manager.resorts 
            if r.get('enabled', False)
        ]
        
        # 应用 limit
        if limit:
            resorts_to_collect = resorts_to_collect[:limit]
        
        print(f"开始采集 {len(resorts_to_collect)} 个雪场")
        
        results = []
        failed_resorts = []
        
        for resort_config in resorts_to_collect:
            resort_name = resort_config.get('name')
            print(f"📍 采集: {resort_name}")
            
            try:
                data = manager.collect_resort_data(resort_config)
                if data:
                    results.append(data)
                else:
                    failed_resorts.append({'name': resort_name, 'error': 'Collection returned None'})
            except Exception as e:
                failed_resorts.append({'name': resort_name, 'error': str(e)})
                print(f"  ❌ 失败: {e}")
        
        # 保存数据
        if results:
            manager.save_data(results)
        
        # 生成报告
        end_time = datetime.now()
        total_count = len(resorts_to_collect)
        success_count = len(results)
        fail_count = len(failed_resorts)
        
        stats = {
            'start_time': start_time,
            'end_time': end_time,
            'total_resorts': total_count,
            'success_count': success_count,
            'fail_count': fail_count,
            'failed_resorts': failed_resorts,
            'data_quality': {}
        }
        
        report_url = generate_and_upload_report(report_generator, stats)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Collected {success_count} resorts successfully',
                'total_resorts': total_count,
                'success_count': success_count,
                'fail_count': fail_count,
                'report_url': report_url
            })
        }
        
    except Exception as e:
        print(f"❌ 采集失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 生成错误报告
        end_time = datetime.now()
        stats = {
            'start_time': start_time,
            'end_time': end_time,
            'total_resorts': 0,
            'success_count': 0,
            'fail_count': 1,
            'failed_resorts': [{'name': 'System Error', 'error': str(e)}],
            'data_quality': {}
        }
        try:
            generate_and_upload_report(report_generator, stats)
        except:
            pass  # 忽略报告生成失败
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'errorType': type(e).__name__
            })
        }

def generate_and_upload_report(report_generator, stats):
    """生成并上传报告"""
    try:
        # 生成报告 HTML
        html_content = report_generator.generate_report_html(stats)
        
        # 生成文件名: report_20251110_120530.html
        timestamp = stats['start_time'].strftime('%Y%m%d_%H%M%S')
        filename = f"report_{timestamp}.html"
        
        # 上传报告
        report_url = report_generator.upload_report(html_content, filename)
        print(f"✅ 报告已生成: {report_url}")
        
        # 更新索引页面
        report_generator.update_index()
        print(f"✅ 索引页面已更新")
        
        return report_url
    except Exception as e:
        print(f"⚠️  报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None
EOF

# 5. 打包
echo "📦 打包..."
cd collector_package
zip -r ../collector-lambda.zip . > /dev/null
cd ..

# 6. 上传到 S3
echo "☁️  上传到 S3..."
BUCKET=$(cd terraform && terraform output -raw lambda_artifacts_bucket)
aws s3 cp collector-lambda.zip "s3://${BUCKET}/collector-lambda.zip" --profile pp --region us-west-2

# 7. 更新 Lambda 函数代码
echo "🔄 更新 Lambda 函数代码..."
aws lambda update-function-code \
  --function-name resort-data-collector \
  --s3-bucket "$BUCKET" \
  --s3-key "collector-lambda.zip" \
  --profile pp \
  --region us-west-2 > /dev/null

echo "⏳ 等待 Lambda 更新完成..."
aws lambda wait function-updated \
  --function-name resort-data-collector \
  --profile pp \
  --region us-west-2

# 8. 清理
echo "🧹 清理临时文件..."
rm -rf collector_package collector-lambda.zip

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                          ✅ 完成!                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Lambda 函数已更新并包含："
echo "  ✅ 联系信息采集 (address, city, zip_code, phone, website)"
echo "  ✅ Open-Meteo API 延迟优化 (避免 429 错误)"
echo "  ✅ 最新的 normalizer 逻辑"
echo ""
echo "测试部署:"
echo "  aws lambda invoke --function-name resort-data-collector --payload '{\"limit\": 5}' --cli-binary-format raw-in-base64-out --profile pp --region us-west-2 response.json"
echo ""

