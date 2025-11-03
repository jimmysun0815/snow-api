#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS Lambda Handler
将 Flask API 适配到 Lambda
"""

from api import app
import serverless_wsgi

def lambda_handler(event, context):
    """
    Lambda 入口函数
    使用 serverless-wsgi 将 Flask 请求转换为 Lambda 响应
    """
    return serverless_wsgi.handle_request(app, event, context)

