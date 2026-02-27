#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询未来3天降雪最多的前20个雪场排名（EC2 部署版）
从数据库读取雪场最新天气预报，按未来3天降雪量排序并打印排名。
支持生成「逐风雪况」小红书图片（2张，每张10个雪场）。

部署路径：/home/ubuntu/.openclaw/workspace/steponsnow/weather_report/
背景图、字体、生成图片均放在该目录。
"""

# =============================================================================
# 配置参数（请按需填写）
# =============================================================================

# ---------- EC2 工作目录（背景图、字体、生成图片均放此目录）----------
WORKSPACE_DIR = "/home/ubuntu/.openclaw/workspace/steponsnow/weather_report"

# ---------- 跳板机（Bastion）信息 ----------
JUMP_HOST = "52.12.212.207"              # 跳板机 IP 或域名
JUMP_PORT = 22                           # 跳板机 SSH 端口
JUMP_USER = "ubuntu"                    # 跳板机 SSH 用户名
JUMP_PKEY_PATH = ""                     # EC2 上私钥路径，例如：/home/ubuntu/.openclaw/workspace/steponsnow/weather_report/snowapp-jump-server.pem
JUMP_PASSWORD = ""                      # 跳板机 SSH 密码（当 JUMP_PKEY_PATH 为空时可填）

# ---------- RDS 数据库信息 ----------
RDS_HOST = "resort-data-postgres.c96os4eq6dgq.us-west-2.rds.amazonaws.com"
RDS_PORT = 5432
RDS_USER = "app"
RDS_PASSWORD = "dCti++8PbdW6kdWW"
RDS_DB = "snow"

# ---------- 连接方式 ----------
USE_JUMP = True

# =============================================================================

import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import date, datetime
from urllib.parse import quote_plus

_workspace_dir = WORKSPACE_DIR

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def _get_database_url():
    """直连数据库 URL，使用文件内 RDS_* 配置。"""
    pw = quote_plus(RDS_PASSWORD) if RDS_PASSWORD else ""
    return f"postgresql://{RDS_USER}:{pw}@{RDS_HOST}:{RDS_PORT}/{RDS_DB}"


def _build_db_url(host, port, user, password, db):
    """拼接 PostgreSQL URL，密码做 URL 编码。"""
    pw = quote_plus(password) if password else ""
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


def _pick_free_port():
    """分配一个本机空闲端口，用于 SSH 本地转发。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _connect_via_jump_and_query(limit=20):
    """
    通过跳板机建立 SSH 隧道（系统 ssh -L），连接 RDS 并执行查询。
    使用系统自带的 ssh，不依赖 paramiko/sshtunnel，避免 DSSKey 等兼容性问题。
    """
    if not JUMP_HOST or not RDS_HOST or not RDS_USER:
        raise ValueError("使用跳板机时请填写 JUMP_HOST、RDS_HOST、RDS_USER（及认证信息）")

    if not JUMP_PKEY_PATH or not os.path.isfile(JUMP_PKEY_PATH):
        raise ValueError(
            "通过跳板机访问请填写 JUMP_PKEY_PATH（私钥路径）。"
            "仅密码认证暂不支持，请使用 ssh 私钥（RSA/Ed25519 等）。"
        )

    local_port = _pick_free_port()
    ssh_cmd = [
        "ssh",
        "-N",
        "-L", f"127.0.0.1:{local_port}:{RDS_HOST}:{RDS_PORT}",
        "-i", JUMP_PKEY_PATH,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=15",
        "-p", str(JUMP_PORT),
        f"{JUMP_USER}@{JUMP_HOST}",
    ]
    proc = subprocess.Popen(
        ssh_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(1.5)  # 等待隧道建立
        if proc.poll() is not None:
            _, stderr = proc.communicate(timeout=2)
            err = (stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError(f"SSH 隧道启动失败: {err or '进程已退出'}")

        url = _build_db_url("127.0.0.1", local_port, RDS_USER, RDS_PASSWORD, RDS_DB)
        engine = create_engine(url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            subq = (
                session.query(
                    ResortWeather.resort_id,
                    func.max(ResortWeather.timestamp).label("max_ts"),
                )
                .group_by(ResortWeather.resort_id)
                .subquery()
            )
            rows = (
                session.query(Resort, ResortWeather)
                .join(ResortWeather, Resort.id == ResortWeather.resort_id)
                .join(
                    subq,
                    (ResortWeather.resort_id == subq.c.resort_id)
                    & (ResortWeather.timestamp == subq.c.max_ts),
                )
                .filter(Resort.enabled == True)
                .all()
            )
        finally:
            session.close()

        results = []
        for resort, weather in rows:
            snowfall_3d = snowfall_next_3_days(weather.forecast_7d)
            results.append((resort, snowfall_3d))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except ProcessLookupError:
                pass


class Resort(Base):
    """雪场表（本脚本仅用到的列，与 DB 表 resorts 对应）"""
    __tablename__ = "resorts"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    location = Column(String(200))
    enabled = Column(Boolean, default=True)


class ResortWeather(Base):
    """雪场天气表（本脚本仅用到的列，与 DB 表 resort_weather 对应）"""
    __tablename__ = "resort_weather"
    id = Column(Integer, primary_key=True)
    resort_id = Column(Integer, ForeignKey("resorts.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)
    forecast_7d = Column(JSON)  # 7天预报（实际可能为15天）


def _get_lantinghei_bold_path():
    """返回 Lantinghei 加粗/Demibold 字体路径。优先工作目录及工作目录下 fonts。"""
    for d in (_workspace_dir, os.path.join(_workspace_dir, "fonts")):
        try:
            if not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                lower = name.lower()
                if ("demibold" in lower or "bold" in lower) and lower.endswith((".ttf", ".ttc", ".otf")):
                    p = os.path.join(d, name)
                    if os.path.isfile(p):
                        return p
        except OSError:
            continue
    if sys.platform == "darwin":
        for p in (
            "/Library/Fonts/Lantinghei SC Demibold.ttf",
            "/System/Library/Fonts/Supplemental/Lantinghei SC.ttc",
            "/System/Library/Fonts/Lantinghei SC.ttc",
            "/Library/Fonts/Lantinghei SC.ttc",
        ):
            if os.path.isfile(p):
                return p
    return None


def _get_chinese_font():
    """返回支持中文的字体路径。工作目录内字体优先，再系统字体。"""
    # 工作目录下 Lantinghei SC.ttf 或任意 .ttf/.ttc/.otf
    for name in ("Lantinghei SC.ttf", "Lantinghei SC.ttc", "Lantinghei SC Demibold.ttf"):
        p = os.path.join(_workspace_dir, name)
        if os.path.isfile(p):
            return p
    for d in (_workspace_dir, os.path.join(_workspace_dir, "fonts")):
        if os.path.isdir(d):
            for name in os.listdir(d):
                if name.lower().endswith((".ttf", ".ttc", ".otf")):
                    p = os.path.join(d, name)
                    if os.path.isfile(p):
                        return p
    candidates = []
    if sys.platform == "darwin":
        # Lantinghei SC（兰亭黑）多路径，再 PingFang、Heiti
        candidates = [
            "/System/Library/Fonts/Lantinghei SC.ttc",
            "/System/Library/Fonts/Lantinghei SC Regular.ttf",
            "/System/Library/Fonts/Supplemental/Lantinghei SC.ttf",
            "/System/Library/Fonts/Supplemental/Lantinghei SC.ttc",
            "/Library/Fonts/Lantinghei SC.ttc",
            "/Library/Fonts/Lantinghei SC Regular.ttf",
            "/Library/Fonts/Lantinghei SC Demibold.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    elif sys.platform == "win32":
        candidates = [
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "msyh.ttc"),
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "msyhbd.ttc"),
        ]
    else:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
        ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _get_logo_path():
    """返回 logo 图片路径，在工作目录下查找。"""
    for name in ("逐风定稿-02.png", "逐风定稿-02.jpg", "逐风定稿-01.png", "逐风定稿-01.jpg"):
        p = os.path.join(_workspace_dir, name)
        if os.path.isfile(p):
            return p
    return None


def _get_sample_svg_path():
    """report-sample.svg 路径（若需要）。"""
    return os.path.join(_workspace_dir, "report-sample.svg")


def _get_report_bg_path(output_dir=None):
    """report_bg.png 路径，在 output_dir 或工作目录下。"""
    base = (output_dir or _workspace_dir) if output_dir is not None else _workspace_dir
    p = os.path.join(base, "report_bg.png")
    return p if os.path.isfile(p) else None


# 地区缩写（美国州、加拿大省等，雪场常用）
_REGION_ABBREV = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Montana": "MT", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oregon": "OR", "Pennsylvania": "PA", "South Dakota": "SD", "Tennessee": "TN",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
    "British Columbia": "BC", "Alberta": "AB", "Quebec": "QC", "Ontario": "ON",
}
# 国家缩写
_COUNTRY_ABBREV = {
    "USA": "US", "United States": "US", "United States of America": "US",
    "Canada": "CA", "Japan": "JP", "China": "CN", "France": "FR", "Italy": "IT",
    "Switzerland": "CH", "Austria": "AT", "Germany": "DE", "Spain": "ES",
    "Australia": "AU", "New Zealand": "NZ", "South Korea": "KR", "Russia": "RU",
}


def _abbreviate_region(region):
    """地区用缩写，如 Washington -> WA。"""
    if not region or not region.strip():
        return ""
    s = region.strip()
    return _REGION_ABBREV.get(s, _REGION_ABBREV.get(s.title(), s[:4] if len(s) > 4 else s))


def _abbreviate_country(country):
    """国家用缩写，如 USA -> US。"""
    if not country or not country.strip():
        return ""
    s = country.strip()
    return _COUNTRY_ABBREV.get(s, _COUNTRY_ABBREV.get(s.title(), s[:3] if len(s) > 3 else s))


def parse_location(location):
    """从 location 字符串解析出地区和国家。格式一般为 "地区, 国家"。"""
    if not location or not location.strip():
        return "", ""
    parts = [p.strip() for p in location.split(",", 1)]
    region = parts[0] if len(parts) > 0 else ""
    country = parts[1] if len(parts) > 1 else ""
    return region, country


def snowfall_next_3_days(forecast_7d):
    """
    从 forecast_7d（实际为15天预报）JSON 中取前3天的 snowfall 并累加，单位：厘米。
    若为 None 或非列表则返回 0.0。
    """
    if forecast_7d is None or not isinstance(forecast_7d, list):
        return 0.0
    total = 0.0
    for i in range(min(3, len(forecast_7d))):
        day = forecast_7d[i]
        if isinstance(day, dict) and "snowfall" in day and day["snowfall"] is not None:
            try:
                total += float(day["snowfall"])
            except (TypeError, ValueError):
                pass
    return total


def get_top_snowfall_resorts(limit=20):
    """
    查询未来3天降雪最多的前 limit 名雪场。
    返回列表 [(resort, snowfall_3d_cm), ...]，按降雪量降序。
    若配置了 USE_JUMP 且 JUMP_HOST 非空，则经跳板机建隧道访问 RDS；否则直连。
    """
    if USE_JUMP and JUMP_HOST:
        return _connect_via_jump_and_query(limit=limit)

    url = _get_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        subq = (
            session.query(
                ResortWeather.resort_id,
                func.max(ResortWeather.timestamp).label("max_ts"),
            )
            .group_by(ResortWeather.resort_id)
            .subquery()
        )
        rows = (
            session.query(Resort, ResortWeather)
            .join(ResortWeather, Resort.id == ResortWeather.resort_id)
            .join(
                subq,
                (ResortWeather.resort_id == subq.c.resort_id)
                & (ResortWeather.timestamp == subq.c.max_ts),
            )
            .filter(Resort.enabled == True)
            .all()
        )
    finally:
        session.close()

    results = []
    for resort, weather in rows:
        snowfall_3d = snowfall_next_3_days(weather.forecast_7d)
        results.append((resort, snowfall_3d))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


# 默认图片输出目录：与工作目录一致，生成图片写在此目录
DEFAULT_OUTPUT_DIR = _workspace_dir


# report_bg.png 上按截图添加文字：顶部标题、日期/副标题与表格左右对齐、排行表居中，字体 Lantinghei
_BG_COLOR = (0xF2, 0xF8, 0xFF)
_TEXT_COLOR = (0x2A, 0x2A, 0x2A)  # 深灰黑
_TITLE_COLOR = (0x6B, 0x93, 0xE7)  # 标题蓝色 #6B93E7
_W = 1080
_H = 1440
_TITLE_Y = 100   # 顶部「逐风雪况」上移，避免与 logo 行重合
_DATE_Y = 320
_SUBTITLE_Y = 320
# 日期/副标题相对表格内收 _DATE_SUBTITLE_INSET，在 _draw_one_image 里用 table_left/right 计算
_DATE_SUBTITLE_INSET = 50   # 日期、副标题往表格内侧收一点
_TABLE_HEADER_Y = 380
_TABLE_FIRST_ROW_Y = 492   # 表头与首行间距加大，避免重叠
_ROW_HEIGHT = 88
# 第一列加宽避免「排名」与「雪场名称」列重叠，总宽不变保证整体居中
_TABLE_COL_WIDTHS = [72, 338, 180, 120, 100]
_TABLE_TOTAL_WIDTH = sum(_TABLE_COL_WIDTHS)
# 排行表字号（海报感、更大）
_TABLE_HEADER_SIZE = 30
_TABLE_BODY_SIZE = 28
_SUB_SIZE = 28
_TITLE_SIZE = 56


def _date_chinese(d):
    """格式化为中文日期，如 2026年1月28日"""
    return f"{d.year}年{d.month}月{d.day}日"


def _draw_one_image(rows, output_path, logo_path, font_path, date_str=None, title="逐风雪况", subtitle="未来三天雪况", report_bg_path=None):
    """
    用 report_bg.png 做底图，在其上添加：顶部标题「逐风雪况」（蓝 #6B93E7、加粗、靠上）、
    日期与「未来三天降雪」与排行榜左右对齐、排行表（居中、Lantinghei、更大字号）。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("生成图片需要 Pillow，请执行: pip install Pillow")

    img = None
    if report_bg_path and os.path.isfile(report_bg_path):
        try:
            img = Image.open(report_bg_path).convert("RGB")
            if img.size != (_W, _H):
                img = img.resize((_W, _H), Image.Resampling.LANCZOS)
        except Exception:
            pass

    if img is None:
        img = Image.new("RGB", (_W, _H), color=_BG_COLOR)

    draw = ImageDraw.Draw(img)
    table_left = (_W - _TABLE_TOTAL_WIDTH) // 2
    col_x = [table_left]
    for w in _TABLE_COL_WIDTHS[:-1]:
        col_x.append(col_x[-1] + w)
    table_right = table_left + _TABLE_TOTAL_WIDTH

    def _load_font(path, size, bold=False):
        if not path or not os.path.isfile(path):
            return None
        # .ttc 为字体集合：index 0 常为 Regular，1 为 Bold/Demibold，先试 0 再试 1
        if path.lower().endswith(".ttc"):
            for idx in (0, 1):
                try:
                    return ImageFont.truetype(path, size, index=idx)
                except Exception:
                    continue
            return None
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return None

    # 标题与排行榜：优先 Lantinghei 加粗（Demibold），颜色 #6B93E7
    font_title = None
    bold_path = _get_lantinghei_bold_path()
    if bold_path:
        font_title = _load_font(bold_path, _TITLE_SIZE)
    if font_title is None and font_path:
        font_title = _load_font(font_path, _TITLE_SIZE)
    if font_title is None:
        font_title = ImageFont.load_default()

    font_sub = _load_font(font_path, _SUB_SIZE) if font_path else None
    font_table = _load_font(font_path, _TABLE_BODY_SIZE) if font_path else None
    font_header = _load_font(font_path, _TABLE_HEADER_SIZE) if font_path else None
    if font_sub is None:
        font_sub = ImageFont.load_default()
    if font_table is None:
        font_table = ImageFont.load_default()
    if font_header is None:
        font_header = font_table

    # 用代码模拟加粗：同一文字画两次，第二次偏移 1 像素，只用于排行榜
    def draw_text_bold(x, y, text, font, fill):
        draw.text((x, y), text, fill=fill, font=font)
        draw.text((x + 1, y), text, fill=fill, font=font)

    # 顶部标题「逐风雪况」居中、蓝色、代码模拟加粗、靠上（避免与 logo 重合）
    title_text = title
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = bbox[2] - bbox[0]
    title_x = (_W - title_w) // 2
    draw_text_bold(title_x, _TITLE_Y, title_text, font_title, _TITLE_COLOR)

    d = date.today() if date_str is None else None
    if d is not None:
        date_display = _date_chinese(d)
    else:
        date_display = date_str or date.today().isoformat()

    # 日期：在排行榜左缘内侧一点（往里收）
    date_x = table_left + _DATE_SUBTITLE_INSET
    draw.text((date_x, _DATE_Y), date_display, fill=_TEXT_COLOR, font=font_sub)

    # 副标题「未来三天降雪」：在排行榜右缘内侧一点（往里收）
    sub_text = "未来三天降雪"
    bbox = draw.textbbox((0, 0), sub_text, font=font_sub)
    sub_w = bbox[2] - bbox[0]
    draw.text((table_right - _DATE_SUBTITLE_INSET - sub_w, _SUBTITLE_Y), sub_text, fill=_TEXT_COLOR, font=font_sub)

    # 表头行（与数据列对齐、居中，代码模拟加粗）
    header_cells = ("排名", "雪场名称", "地区", "国家", "降雪量")
    for j, cell in enumerate(header_cells):
        draw_text_bold(col_x[j], _TABLE_HEADER_Y, cell, font_header, _TEXT_COLOR)

    for i, (rank, name, region, country, snowfall_cm) in enumerate(rows):
        y = _TABLE_FIRST_ROW_Y + i * _ROW_HEIGHT
        name_s = (name or "")[:18]
        region_s = (region or "")[:12]
        country_s = (country or "")[:8]
        snow_s = f"{snowfall_cm:.1f}cm" if snowfall_cm is not None else "-"
        for j, cell in enumerate((str(rank), name_s, region_s, country_s, snow_s)):
            draw_text_bold(col_x[j], y, cell, font_table, _TEXT_COLOR)

    img.save(output_path, "PNG")
    return output_path


def render_snowfall_images(top_20_list, output_dir=None, logo_path=None):
    """
    根据前 20 名雪场数据生成两张图：逐风雪况_YYYY-MM-DD_1.png、逐风雪况_YYYY-MM-DD_2.png。
    底图使用 report_bg.png（背景已含 logo），只在其上添加日期、副标题、排行数据。
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    report_bg_path = _get_report_bg_path(output_dir)
    if not report_bg_path:
        print("警告: 未找到 report_bg.png，将使用纯色背景。请将 report_bg.png 放在输出目录或设置 SNOWFALL_REPORT_BG。", file=sys.stderr)
    font_path = _get_chinese_font()
    if not font_path:
        print("警告: 未找到中文字体（Lantinghei），图片中的中文可能显示为方框。可设置 SNOWFALL_IMAGE_FONT_PATH。", file=sys.stderr)

    date_str = date.today().isoformat()

    def row_data(resort, snowfall_3d):
        region, country = parse_location(resort.location)
        name = (resort.name or "").strip()
        return name, _abbreviate_region(region), _abbreviate_country(country), snowfall_3d

    for idx, start in enumerate([0, 10], start=1):
        chunk = top_20_list[start : start + 10]
        rows = []
        for r, (resort, snowfall_3d) in enumerate(chunk, start=start + 1):
            name, region, country, snow = row_data(resort, snowfall_3d)
            rows.append((r, name, region, country, snow))
        if not rows:
            continue
        out_name = f"逐风雪况_{date_str}_{idx}.png"
        out_path = os.path.join(output_dir, out_name)
        _draw_one_image(rows, out_path, None, font_path, date_str=date_str, report_bg_path=report_bg_path)
        print(f"已生成: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="未来3天降雪最多的前20雪场排名，并可生成逐风雪况小红书图片")
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="只打印排名，不生成图片",
    )
    parser.add_argument(
        "--images-only",
        action="store_true",
        help="只生成图片，不打印排名（仍会查库取前20）",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="图片输出目录，默认为 backend-api/daily_report",
    )
    parser.add_argument(
        "--logo",
        default=None,
        help="Logo 图片路径，默认使用项目 marketing/logo/逐风定稿-01.png",
    )
    args = parser.parse_args()

    print("正在查询数据库：未来3天降雪最多的雪场…")
    try:
        top = get_top_snowfall_resorts(limit=20)
    except Exception as e:
        print(f"数据库查询失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.images_only:
        # 表头
        print()
        print("=" * 80)
        print("未来3天降雪量排名（前20名）")
        print("=" * 80)
        print(f"{'排名':<6}{'雪场名称':<28}{'地区':<22}{'国家':<14}{'降雪量 (cm)':<12}")
        print("-" * 80)

        for rank, (resort, snowfall_3d) in enumerate(top, start=1):
            region, country = parse_location(resort.location)
            name = (resort.name or "")[:26]
            region_s = _abbreviate_region(region) or (region or "")[:20]
            country_s = _abbreviate_country(country) or (country or "")[:12]
            snowfall_s = f"{snowfall_3d:.1f}" if snowfall_3d is not None else "-"
            print(f"{rank:<6}{name:<28}{region_s:<22}{country_s:<14}{snowfall_s:<12}")

        print("=" * 80)

    if not args.no_images:
        out_dir = args.output_dir or DEFAULT_OUTPUT_DIR
        try:
            render_snowfall_images(top, output_dir=out_dir, logo_path=args.logo)
        except Exception as e:
            print(f"图片未生成: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
