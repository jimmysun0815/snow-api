#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产环境雪道数据更新脚本
连接到 AWS RDS 数据库并更新雪道数据
"""

import os
import sys
import argparse
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from collect_trails import main as collect_trails_main
from db_manager import DatabaseManager


def setup_prod_env():
    """设置生产环境变量"""
    print("\n" + "="*80)
    print("🌩️  配置生产环境连接")
    print("="*80)
    print()
    
    # 获取 Terraform 输出
    import subprocess
    import json
    
    try:
        # 切换到 terraform 目录
        terraform_dir = Path(__file__).parent / 'terraform'
        
        print("📡 从 Terraform 获取生产环境配置...")
        
        # 获取 RDS 端点
        result = subprocess.run(
            ['terraform', 'output', '-json', 'rds_endpoint'],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        rds_endpoint = json.loads(result.stdout)
        
        # 获取 Redis 端点
        result = subprocess.run(
            ['terraform', 'output', '-json', 'redis_endpoint'],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        redis_endpoint = json.loads(result.stdout)
        
        print(f"✅ RDS 端点: {rds_endpoint}")
        print(f"✅ Redis 端点: {redis_endpoint}")
        print()
        
        # 从 terraform.tfvars 读取数据库密码
        tfvars_file = terraform_dir / 'terraform.tfvars'
        db_password = None
        
        if tfvars_file.exists():
            with open(tfvars_file, 'r') as f:
                for line in f:
                    if 'db_password' in line and '=' in line:
                        db_password = line.split('=')[1].strip().strip('"')
                        break
        
        if not db_password:
            print("❌ 无法从 terraform.tfvars 读取数据库密码")
            db_password = input("请输入数据库密码: ")
        
        # 设置环境变量
        os.environ['POSTGRES_HOST'] = rds_endpoint.split(':')[0]
        os.environ['POSTGRES_PORT'] = '5432'
        os.environ['POSTGRES_USER'] = 'app'
        os.environ['POSTGRES_PASSWORD'] = db_password
        os.environ['POSTGRES_DB'] = 'snow'
        
        os.environ['REDIS_HOST'] = redis_endpoint.split(':')[0]
        os.environ['REDIS_PORT'] = '6379'
        os.environ['REDIS_DB'] = '0'
        
        os.environ['ENVIRONMENT'] = 'production'
        
        print("✅ 环境变量已设置")
        print()
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 获取 Terraform 输出失败: {e}")
        print()
        print("请手动设置环境变量:")
        print("  export POSTGRES_HOST=<RDS端点>")
        print("  export POSTGRES_PASSWORD=<数据库密码>")
        print("  export REDIS_HOST=<Redis端点>")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def verify_connection():
    """验证数据库连接"""
    print("🔍 验证数据库连接...")
    
    try:
        db = DatabaseManager()
        
        # 测试查询
        with db.engine.connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM resorts")
            count = result.scalar()
            print(f"✅ 连接成功! 数据库中有 {count} 个雪场")
            
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生产环境雪道数据更新工具')
    parser.add_argument(
        '--resort-id',
        type=int,
        help='只更新指定 ID 的雪场'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='限制更新数量'
    )
    parser.add_argument(
        '--skip-verify',
        action='store_true',
        help='跳过确认提示'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🏔️  生产环境雪道数据更新工具")
    print("="*80)
    print()
    
    # 设置生产环境
    if not setup_prod_env():
        print("❌ 无法配置生产环境，退出")
        sys.exit(1)
    
    # 验证连接
    if not verify_connection():
        print("❌ 无法连接到生产数据库，退出")
        sys.exit(1)
    
    print()
    
    # 确认提示
    if not args.skip_verify:
        print("⚠️  警告: 即将更新生产环境数据!")
        print()
        
        if args.resort_id:
            print(f"   将更新雪场 ID: {args.resort_id}")
        elif args.limit:
            print(f"   将更新前 {args.limit} 个雪场")
        else:
            print(f"   将更新所有雪场 (约 309 个)")
        
        print()
        response = input("确认继续? (输入 'yes' 继续): ")
        
        if response.lower() != 'yes':
            print("❌ 已取消")
            sys.exit(0)
    
    print()
    print("="*80)
    print("🚀 开始采集雪道数据...")
    print("="*80)
    print()
    
    # 准备参数
    original_argv = sys.argv.copy()
    sys.argv = ['collect_trails.py']
    
    if args.resort_id:
        sys.argv.extend(['--resort-id', str(args.resort_id)])
    
    if args.limit:
        sys.argv.extend(['--limit', str(args.limit)])
    
    # 运行采集
    try:
        collect_trails_main()
        print()
        print("="*80)
        print("✅ 生产环境雪道数据更新完成!")
        print("="*80)
        
    except KeyboardInterrupt:
        print()
        print("⚠️  用户中断")
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"❌ 更新失败: {e}")
        sys.exit(1)
        
    finally:
        sys.argv = original_argv


if __name__ == '__main__':
    main()

