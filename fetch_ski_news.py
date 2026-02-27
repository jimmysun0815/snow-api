#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拉取美国、加拿大滑雪场相关新闻（NewsData.io Latest API）

推荐用法：只限美加来源 + 滑雪/雪场关键词，减少无关 resort（如海湖庄园）、欧洲雪场等。

推荐 API 参数：
  - country=us,ca    只取美国、加拿大来源（最多 5 国，Free/Basic 支持）
  - q=ski resort    比 "snow resort" 更准，避免误匹配其他 resort
  - 可选 category=tourism  更精准但条数会变少
  - removeduplicate=1  去重
  - language=en  可选，只要英文

直接请求「最佳」URL 示例（请替换 YOUR_API_KEY）：
  https://newsdata.io/api/1/latest?apikey=YOUR_API_KEY&q=ski+resort&country=us,ca&category=tourism&language=en&removeduplicate=1
"""

import json
import os
import urllib.parse
import urllib.request
from typing import Optional

import argparse


NEWSDATA_LATEST_URL = "https://newsdata.io/api/1/latest"


def build_ski_news_url(
    apikey: str,
    *,
    country: str = "us,ca",
    q: str = "ski resort",
    category: Optional[str] = "tourism",
    language: str = "en",
    removeduplicate: int = 1,
    size: Optional[int] = None,
) -> str:
    """构建「美加滑雪场新闻」请求 URL。"""
    params = {
        "apikey": apikey,
        "q": q,
        "country": country,
        "language": language,
        "removeduplicate": removeduplicate,
    }
    if category:
        params["category"] = category
    if size is not None:
        params["size"] = size
    return NEWSDATA_LATEST_URL + "?" + urllib.parse.urlencode(params)


def fetch_ski_news(
    apikey: Optional[str] = None,
    *,
    country: str = "us,ca",
    q: str = "ski resort",
    category: Optional[str] = "tourism",
    language: str = "en",
    removeduplicate: int = 1,
    size: Optional[int] = None,
) -> dict:
    """
    请求美加滑雪场相关新闻。

    :param apikey: NewsData.io API Key，不传则读环境变量 NEWSDATA_API_KEY
    :param country: 国家，默认 us,ca（美国+加拿大）
    :param q: 搜索关键词，默认 "ski resort"
    :param category: 分类，默认 "tourism" 更精准；传 None 可获更多条数但噪音多
    :param language: 语言，默认 en
    :param removeduplicate: 是否去重，默认 1
    :param size: 每页条数（免费 10，付费最多 50），不传用 API 默认
    :return: API 返回的 JSON 字典，含 status, totalResults, results 等
    """
    key = apikey or os.environ.get("NEWSDATA_API_KEY", "")
    if not key:
        raise ValueError("请设置 NEWSDATA_API_KEY 或传入 apikey")
    url = build_ski_news_url(
        key,
        country=country,
        q=q,
        category=category,
        language=language,
        removeduplicate=removeduplicate,
        size=size,
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(description="拉取美加滑雪场相关新闻")
    parser.add_argument("--apikey", default=os.environ.get("NEWSDATA_API_KEY", ""), help="NewsData.io API Key")
    parser.add_argument("--country", default="us,ca", help="国家，逗号分隔，默认 us,ca")
    parser.add_argument("--q", default="ski resort", help="搜索关键词")
    parser.add_argument("--no-category", action="store_true", help="不加 category，结果更多但噪音多")
    parser.add_argument("--size", type=int, default=None, help="每页条数（免费 10，付费最多 50）")
    parser.add_argument("--json", action="store_true", help="只输出原始 JSON")
    args = parser.parse_args()

    if not args.apikey:
        print("错误: 请设置环境变量 NEWSDATA_API_KEY 或使用 --apikey")
        return 1

    data = fetch_ski_news(
        apikey=args.apikey,
        country=args.country,
        q=args.q,
        category=None if args.no_category else "tourism",
        size=args.size,
    )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    status = data.get("status")
    total = data.get("totalResults", 0)
    results = data.get("results") or []
    print(f"status: {status} | totalResults: {total} | 本页: {len(results)} 条\n")
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        desc = (r.get("description") or "")[:140]
        countries = r.get("country", [])
        source = r.get("source_name", "")
        pub = r.get("pubDate", "")
        link = r.get("link", "")
        print(f"{i}. [{', '.join(countries)}] {title}")
        print(f"   {desc}")
        print(f"   来源: {source} | {pub}")
        print(f"   {link}\n")
    return 0


if __name__ == "__main__":
    exit(main() or 0)
