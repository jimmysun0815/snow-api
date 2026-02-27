#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时预热 Lambda：每小时请求 /api/resorts/summary，保持 Redis 缓存有效。
由 EventBridge 在每小时第 10 分钟触发。
"""
import os
import urllib.request
import json


def lambda_handler(event, context):
    api_url = os.environ.get("API_URL", "https://api.steponsnow.com").rstrip("/")
    url = f"{api_url}/api/resorts/summary"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ResortData-Warmup/1.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read()
            data = json.loads(body.decode())
            count = len(data.get("resorts", []))
            print(f"[Warmup] GET {url} -> {resp.status}, resorts={count}")
            return {"statusCode": resp.status, "resorts_count": count}
    except Exception as e:
        print(f"[Warmup] GET {url} failed: {e}")
        raise
