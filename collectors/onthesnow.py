#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OnTheSnow 网页采集器

OnTheSnow 已从 Next.js Pages Router 迁到 App Router，页面里不再有
`<script id="__NEXT_DATA__">`，数据改为分块推进 `self.__next_f.push([1, "..."])`
的 React Server Component flight 流里。

采集器把这些分块拼回完整流，再从中切出含 `fullResort` 的那个对象（即旧版的
pageProps），最后仍按 `{'props': {'pageProps': ...}}` 的形状返回，
这样 normalizer.py 不用改。旧格式也仍然兼容，页面万一回退不会失败。
"""

import re
import json
from typing import Optional, Dict
from .base import BaseCollector

# self.__next_f.push([1,"<转义过的 JS 字符串>"])
_NEXT_F_CHUNK_RE = re.compile(
    r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)'
)

# 旧版 Pages Router
_LEGACY_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)

# 页面数据的判定标志：normalizer 只认 fullResort / shortWeather
_ANCHOR_KEY = '"fullResort"'

# 回溯找对象起点的尝试次数上限，防止畸形页面上退化成 O(n^2)
_MAX_BACKTRACK = 500


class OnTheSnowCollector(BaseCollector):
    """OnTheSnow 网页采集器"""

    def collect(self) -> Optional[Dict]:
        """
        从 OnTheSnow 网页采集数据

        Returns:
            {'props': {'pageProps': {...}}} 或 None
        """
        url = self.resort_config.get('source_url')

        if not url:
            self.log('ERROR', '缺少 source_url 配置')
            return None

        self.log('INFO', f'开始采集数据: {url}')

        # 添加小延迟，避免被识别为机器人（并发模式下保持较短延迟）
        self.random_delay(0.5, 1.0)

        # 使用带重试的请求方法
        response = self.fetch_with_retry(url, max_retries=3, timeout=15)

        if not response:
            return None

        try:
            page_props = self._extract_page_props(response.text)
        except Exception as e:
            self.log('ERROR', f'解析页面数据时出错: {str(e)}')
            return None

        if page_props is None:
            self.log(
                'ERROR',
                '未能从页面提取雪场数据（__NEXT_DATA__ 与 __next_f 流均未命中，'
                '页面结构可能又变了）',
            )
            return None

        self.log('INFO', '数据采集成功')
        return {'props': {'pageProps': page_props}}

    # ------------------------------------------------------------------

    def _extract_page_props(self, html: str) -> Optional[Dict]:
        """先试旧版 __NEXT_DATA__，再试 App Router 的 flight 流"""
        legacy = self._extract_from_legacy_next_data(html)
        if legacy is not None:
            self.log('INFO', '命中旧版 __NEXT_DATA__')
            return legacy

        return self._extract_from_flight_stream(html)

    def _extract_from_legacy_next_data(self, html: str) -> Optional[Dict]:
        match = _LEGACY_NEXT_DATA_RE.search(html)
        if not match:
            return None

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            self.log('WARNING', f'旧版 __NEXT_DATA__ JSON 解析失败: {e}')
            return None

        page_props = data.get('props', {}).get('pageProps')
        return page_props if isinstance(page_props, dict) else None

    def _extract_from_flight_stream(self, html: str) -> Optional[Dict]:
        """拼回 flight 流，再切出含 fullResort 的对象"""
        chunks = _NEXT_F_CHUNK_RE.findall(html)
        if not chunks:
            return None

        parts = []
        for raw in chunks:
            try:
                # raw 本身就是带引号的 JSON 字符串字面量，直接反转义
                parts.append(json.loads(raw))
            except json.JSONDecodeError:
                # 单个分块坏掉不致命，跳过继续拼
                continue

        stream = ''.join(parts)
        if not stream:
            return None

        return self._slice_object_containing(stream, _ANCHOR_KEY)

    @staticmethod
    def _slice_object_containing(stream: str, anchor: str) -> Optional[Dict]:
        """
        在 stream 里定位 anchor，然后从它往前找最近的、能解析出合法 JSON
        且真正包含该 key 的对象起点。

        flight 流不是单个 JSON 文档，只能这样按对象切。
        """
        anchor_at = stream.find(anchor)
        if anchor_at < 0:
            return None

        decoder = json.JSONDecoder()
        cursor = anchor_at
        for _ in range(_MAX_BACKTRACK):
            cursor = stream.rfind('{', 0, cursor)
            if cursor < 0:
                return None
            try:
                obj, end = decoder.raw_decode(stream, cursor)
            except ValueError:
                continue
            # end > anchor_at 确保切出来的对象真的把 anchor 包在里面，
            # 而不是它前面某个刚好也能解析成功的小对象
            if isinstance(obj, dict) and 'fullResort' in obj and end > anchor_at:
                return obj

        return None
