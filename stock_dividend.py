#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高股息标的股息率查询工具
数据来源: 腾讯财经实时行情接口 (qt.gtimg.cn)
说明: 直接从腾讯行情接口提取股息率(TTM)等核心指标
"""

import requests
import re
import time
import os
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # 无GUI后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

# ===================== 高股息标的完整列表 =====================
STOCK_LIST = [
    # ---- 电力 ----
    ("sz003816", "中国广核"),
    ("sh601985", "中国核电"),
    ("sh600900", "长江电力"),
    ("sh600025", "华能水电"),
    ("sh600886", "国投电力"),
    ("sh600674", "川投能源"),
    ("sh600863", "内蒙华电"),
    ("sh600023", "浙能电力"),
    ("sh600795", "国电电力"),
    # ---- 银行 ----
    ("sh601288", "农业银行"),
    ("sh601398", "工商银行"),
    ("sz002142", "宁波银行"),
    ("sh600036", "招商银行"),
    ("sh601988", "中国银行"),
    ("sh601939", "建设银行"),
    ("sh601328", "交通银行"),
    ("sh601658", "邮储银行"),
    ("sh601838", "成都银行"),
    ("sh600919", "江苏银行"),
    ("sh601169", "北京银行"),
    ("sz000001", "平安银行"),
    ("sh600926", "杭州银行"),
    ("sh601166", "兴业银行"),
    ("sh601818", "光大银行"),
    ("sh600015", "华夏银行"),
    ("sh600016", "民生银行"),
    # ---- 保险 ----
    ("sh601318", "中国平安"),
    ("sh601601", "中国太保"),
    # ---- 白酒 ----
    ("sh600519", "贵州茅台"),
    ("sz000858", "五粮液"),
    ("sz000568", "泸州老窖"),
    ("sh600809", "山西汾酒"),
    # ---- 通讯 ----
    ("sh600941", "中国移动"),
    ("sh601728", "中国电信"),
    # ---- 运输 ----
    ("sh601919", "中远海控"),
    ("sh601006", "大秦铁路"),
    ("sh603565", "中谷物流"),
    ("sh601107", "四川成渝"),
    ("sz001965", "招商公路"),
    # ---- 医疗器械 ----
    ("sz300760", "迈瑞医疗"),
    # ---- 传媒 ----
    ("sz002027", "分众传媒"),
    # ---- 食品饮料 ----
    ("sh600887", "伊利股份"),
    ("sz000895", "双汇发展"),
    # ---- 家电 ----
    ("sz000333", "美的集团"),
    ("sz000651", "格力电器"),
    ("sh600699", "海尔智家"),
    # ---- 煤炭油气 ----
    ("sh601088", "中国神华"),
    ("sh600938", "中国海油"),
    # ---- 小家电 ----
    ("sz002032", "苏泊尔"),
    # ---- 中药 ----
    ("sz000538", "云南白药"),
    ("sz000423", "东阿阿胶"),
    # ---- 服装家纺 ----
    ("sh603558", "健盛集团"),
]


def fetch_tencent_quotes(codes):
    """
    通过腾讯财经实时行情接口批量获取股票数据
    接口: https://qt.gtimg.cn/q=代码1,代码2,...

    返回数据以 ~ 分隔，关键字段索引:
      1:  股票名称       2:  股票代码     3:  当前价
      4:  昨收价         5:  今开价       6:  成交量(手)
     30:  日期时间       31: 涨跌额       32: 涨跌幅%
     38:  换手率%        39: 市盈率(动态)  43: 振幅%
     44:  流通市值(亿)   45: 总市值(亿)    46: 市净率PB
     47:  52周最高       48: 52周最低      49: 量比
     64:  股息率%(TTM)
    """
    url = f"https://qt.gtimg.cn/q={','.join(codes)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.qq.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "gbk"
        return resp.text
    except Exception as e:
        print(f"  [错误] 获取腾讯实时行情失败: {e}")
        return ""


def fetch_year_klines(codes):
    """
    一次查询获取从年初至今的全部日K线数据（合并原 fetch_year_start_price + fetch_recent_klines）
    接口: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
    参数: param=代码,day,开始日期,结束日期,数量,qfq
    K线格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]

    返回: {code: {
        "year_start": {"date": ..., "open": ..., "close": ...},  # 年初第一个交易日
        "kline_closes": [close_1, close_2, ...],                  # 年初至今全部收盘价
    }, ...}
    """
    year = datetime.now().year
    start_date = f"{year}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.qq.com/",
    }
    results = {}
    # 逐只获取(该接口不支持批量)
    for code in codes:
        try:
            url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                   f"?param={code},day,{start_date},{end_date},500,qfq")
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                stock_data = data["data"].get(code, {})
                klines = stock_data.get("qfqday", []) or stock_data.get("day", [])
                if klines and len(klines) > 0:
                    # 第一根K线 = 年初第一个交易日: [日期, 开盘, 收盘, 最高, 最低, 成交量]
                    first_day = klines[0]
                    # 全部K线的收盘价 = 年初至今走势
                    all_closes = [float(k[2]) for k in klines]
                    results[code] = {
                        "year_start": {
                            "date": first_day[0],
                            "open": float(first_day[1]),   # 年初开盘价
                            "close": float(first_day[2]),  # 年初收盘价
                        },
                        "kline_closes": all_closes,
                    }
        except Exception:
            pass
        time.sleep(0.15)  # 控制请求频率
    return results


def parse_quotes(raw_text):
    """解析腾讯行情数据，提取关键字段"""
    results = {}
    pattern = r'v_(\w+)="([^"]*)"'
    for match in re.finditer(pattern, raw_text):
        code = match.group(1)
        data_str = match.group(2)
        if not data_str:
            continue
        fields = data_str.split("~")
        if len(fields) < 65:
            continue

        def safe_float(idx, default=0.0):
            try:
                v = fields[idx].strip()
                return float(v) if v else default
            except (ValueError, IndexError):
                return default

        results[code] = {
            "name": fields[1],
            "code": fields[2],
            "price": safe_float(3),
            "last_close": safe_float(4),
            "open": safe_float(5),
            "change": safe_float(31),
            "change_pct": safe_float(32),
            "turnover_rate": safe_float(38),
            "pe_dynamic": safe_float(39),
            "amplitude": safe_float(43),
            "circ_mv": safe_float(44),       # 流通市值(亿)
            "total_mv": safe_float(45),       # 总市值(亿)
            "pb": safe_float(46),             # 市净率PB
            "high_52w": safe_float(47),       # 52周最高
            "low_52w": safe_float(48),        # 52周最低
            "dividend_yield": safe_float(64), # 股息率%(TTM) ← 关键字段
        }
    return results


def _find_cjk_font():
    """查找系统中可用的中文字体"""
    # macOS 常见中文字体路径
    candidates = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            return fm.FontProperties(fname=fp)
    # 兜底：尝试系统已注册的中文字体名
    for name in ["PingFang SC", "Heiti SC", "STHeiti", "SimHei", "Microsoft YaHei"]:
        try:
            fp = fm.FontProperties(family=name)
            if fm.findfont(fp) != fm.findfont("DejaVu Sans"):
                return fp
        except Exception:
            pass
    return fm.FontProperties()


def _draw_sparkline(ax, x, y, width, height, closes, fig, fig_height):
    """
    在主ax的指定数据坐标区域绘制迷你K线走势图 (sparkline)
    closes: 收盘价列表
    使用 fig.add_axes 创建子坐标系，保证走势图独立、不影响主表格

    因为 ax 的 xlim=[0,1], ylim=[0, fig_height]，
    并且 subplots_adjust(left=0, right=1, top=1, bottom=0)，
    所以 data coords 与 figure fraction 的关系是简单的线性映射:
        fig_x = data_x / 1.0 = data_x
        fig_y = data_y / fig_height
    """
    if not closes or len(closes) < 2:
        return

    # 直接通过线性关系计算 figure fraction 坐标
    # ax xlim = [0, 1], 所以 fig_fraction_x = data_x (因为 left=0, right=1)
    # ax ylim = [0, fig_height], 所以 fig_fraction_y = data_y / fig_height (因为 bottom=0, top=1)
    fx0 = x
    fy0 = y / fig_height
    fw = width
    fh = height / fig_height

    # 留一点内边距让走势图不贴边
    pad_x = fw * 0.08
    pad_y = fh * 0.15
    bbox = [fx0 + pad_x, fy0 + pad_y, fw - 2 * pad_x, fh - 2 * pad_y]

    spark_ax = fig.add_axes(bbox)
    spark_ax.set_xlim(0, len(closes) - 1)

    c_min, c_max = min(closes), max(closes)
    margin = (c_max - c_min) * 0.1 if c_max > c_min else 0.5
    spark_ax.set_ylim(c_min - margin, c_max + margin)
    spark_ax.axis("off")

    xs = list(range(len(closes)))

    # 填充区域 — 涨用红色渐变，跌用绿色渐变
    start_val, end_val = closes[0], closes[-1]
    if end_val >= start_val:
        line_color = "#D32F2F"
        fill_color = "#FDEAEA"
    else:
        line_color = "#2E7D32"
        fill_color = "#E8F5E9"

    spark_ax.fill_between(xs, closes, c_min - margin,
                          color=fill_color, alpha=0.6)
    spark_ax.plot(xs, closes, color=line_color, linewidth=1.0, solid_capstyle="round")

    # 标记起点和终点小圆点
    spark_ax.plot(0, closes[0], "o", color="#888888", markersize=1.8)
    spark_ax.plot(len(closes) - 1, closes[-1], "o", color=line_color, markersize=2.2)


def generate_table_image(table_rows, output_path):
    """
    将股息率数据生成一张精美的表格图片
    table_rows: 已按股息率降序排好的数据列表 (每个 row 需含 'kline_closes' 字段)
    output_path: 图片保存路径
    """
    font_prop = _find_cjk_font()
    font_prop_bold = font_prop.copy()
    font_prop_bold.set_weight("bold")

    year = datetime.now().year
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---------- 准备表格数据 ----------
    has_score = any("eval_score" in r for r in table_rows)
    if has_score:
        col_headers = ["名称", "代码", "现价", "年初价",
                       "年初至今", "股息率(TTM)", "评分", "评级", "走势(年初至今)", "PE", "PB", "市值(亿)"]
    else:
        col_headers = ["名称", "代码", "现价", "年初价",
                       "年初至今", "股息率(TTM)", "走势(年初至今)", "PE", "PB", "市值(亿)"]
    n_cols = len(col_headers)

    # 走势列索引
    sparkline_col_idx = 8 if has_score else 6

    # ---------- 构建带板块分隔行的渲染列表 ----------
    # render_items: list of dict, type="section_header" 或 type="data"
    render_items = []
    from collections import OrderedDict as _OD
    cat_groups = _OD()
    for row in table_rows:
        cat = row["category"]
        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(row)

    rank = 0
    for cat, rows_in_cat in cat_groups.items():
        # 板块标题行
        cat_avg_dv = sum(r["dividend_yield"] for r in rows_in_cat) / len(rows_in_cat)
        render_items.append({
            "type": "section_header",
            "category": cat,
            "count": len(rows_in_cat),
            "avg_dv": cat_avg_dv,
        })
        for row in rows_in_cat:
            rank += 1
            ytd_price_str = f"{row['ytd_price']:.2f}" if row["ytd_price"] > 0 else "--"
            ytd_chg_str = f"{row['ytd_change_pct']:+.2f}%" if row["ytd_price"] > 0 else "--"
            dv_str = f"{row['dividend_yield']:.2f}%"
            mv_str = f"{row['total_mv']:.0f}" if row["total_mv"] >= 1 else f"{row['total_mv']:.2f}"

            if has_score:
                score_val = row.get("eval_score", 0)
                rating_val = row.get("eval_rating", "--")
                cells = [
                    row["name"],
                    row["code"],
                    f"{row['price']:.2f}",
                    ytd_price_str,
                    ytd_chg_str,
                    dv_str,
                    f"{score_val:.1f}" if score_val > 0 else "--",
                    rating_val,
                    "",  # 走势列占位
                    f"{row['pe']:.2f}",
                    f"{row['pb']:.2f}",
                    mv_str,
                ]
            else:
                cells = [
                    row["name"],
                    row["code"],
                    f"{row['price']:.2f}",
                    ytd_price_str,
                    ytd_chg_str,
                    dv_str,
                    "",  # 走势列占位
                    f"{row['pe']:.2f}",
                    f"{row['pb']:.2f}",
                    mv_str,
                ]
            render_items.append({
                "type": "data",
                "row": row,
                "cells": cells,
                "rank": rank,
            })

    n_data_rows = sum(1 for it in render_items if it["type"] == "data")
    n_section_rows = sum(1 for it in render_items if it["type"] == "section_header")
    n_total_visual_rows = n_data_rows + n_section_rows

    # ---------- 颜色方案 ----------
    header_bg = "#1a2a4a"
    header_fg = "#FFFFFF"
    row_bg_even = "#F8FAFD"
    row_bg_odd = "#FFFFFF"
    grid_color = "#D0D8E8"

    # ---------- 计算尺寸 ----------
    if has_score:
        col_widths = [0.075, 0.068, 0.058, 0.058, 0.078, 0.088, 0.058, 0.088, 0.125, 0.058, 0.058, 0.073]
    else:
        col_widths = [0.085, 0.080, 0.070, 0.070, 0.095, 0.110, 0.150, 0.070, 0.070, 0.085]
    fig_width = 20 if has_score else 18
    row_height = 0.42
    section_header_height = 0.36  # 板块标题行高度
    header_height = 0.48
    title_height = 1.0
    footer_height = 0.6
    table_height = header_height + n_data_rows * row_height + n_section_rows * section_header_height
    fig_height = title_height + table_height + footer_height

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, fig_height)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # ---------- 标题区域 ----------
    title_y = fig_height - title_height * 0.45
    ax.text(0.5, title_y, f"高股息标的股息率(TTM)排行榜",
            fontproperties=font_prop_bold, fontsize=20,
            ha="center", va="center", color="#1a2a4a")
    ax.text(0.5, title_y - 0.35,
            f"数据来源: 腾讯财经  |  {now_str}  |  按板块分组, 板块内按股息率排序  |  含年初至今走势",
            fontproperties=font_prop, fontsize=10,
            ha="center", va="center", color="#666666")

    # ---------- 绘制表头 ----------
    table_top = fig_height - title_height
    x_pos = 0.0
    for j, (hdr, w) in enumerate(zip(col_headers, col_widths)):
        rect = plt.Rectangle((x_pos, table_top - header_height), w, header_height,
                              facecolor=header_bg, edgecolor=header_bg, linewidth=0)
        ax.add_patch(rect)
        ax.text(x_pos + w / 2, table_top - header_height / 2, hdr,
                fontproperties=font_prop_bold, fontsize=10,
                ha="center", va="center", color=header_fg)
        x_pos += w

    # ---------- 第一遍：绘制数据行(矩形和文字，不含sparkline) ----------
    dv_values = [r["dividend_yield"] for r in table_rows]
    dv_min = min(dv_values) if dv_values else 0
    dv_max = max(dv_values) if dv_values else 1

    # 收集需要绘制sparkline的单元格位置信息
    sparkline_tasks = []

    # 板块标题行颜色
    section_bg = "#E8EDF5"
    section_fg = "#1a2a4a"

    current_y = table_top - header_height
    data_row_idx = 0  # 用于交替行颜色

    for item in render_items:
        if item["type"] == "section_header":
            # 绘制板块标题行
            row_y = current_y - section_header_height
            total_w = sum(col_widths)
            rect = plt.Rectangle((0, row_y), total_w, section_header_height,
                                  facecolor=section_bg, edgecolor=grid_color, linewidth=0.5)
            ax.add_patch(rect)
            section_label = f"▎{item['category']}  ({item['count']}只, 均值 {item['avg_dv']:.2f}%)"
            ax.text(0.015, row_y + section_header_height / 2, section_label,
                    fontproperties=font_prop_bold, fontsize=10,
                    ha="left", va="center", color=section_fg)
            current_y = row_y
            data_row_idx = 0  # 每个板块重新开始交替颜色
            continue

        # 绘制数据行
        row = item["row"]
        cells = item["cells"]
        row_y = current_y - row_height
        bg = row_bg_even if data_row_idx % 2 == 0 else row_bg_odd
        data_row_idx += 1

        x_pos = 0.0
        for j, (cell, w) in enumerate(zip(cells, col_widths)):
            cell_bg = bg

            # 股息率列特殊着色
            if j == 5:
                dv = row["dividend_yield"]
                if dv >= 6:
                    cell_bg = "#FDEAEA"
                elif dv >= 5:
                    cell_bg = "#FFF3E0"
                elif dv >= 4:
                    cell_bg = "#FFFDE7"
                else:
                    cell_bg = bg

            # 评分列特殊着色
            if has_score and j == 6:
                sv = row.get("eval_score", 0)
                if sv >= 85:
                    cell_bg = "#FDEAEA"   # 深红底
                elif sv >= 75:
                    cell_bg = "#FFF3E0"   # 橙底
                elif sv >= 65:
                    cell_bg = "#FFFDE7"   # 黄底
                else:
                    cell_bg = bg

            rect = plt.Rectangle((x_pos, row_y), w, row_height,
                                  facecolor=cell_bg, edgecolor=grid_color,
                                  linewidth=0.5)
            ax.add_patch(rect)

            # 走势列：先只记录位置，稍后再绘制sparkline
            if j == sparkline_col_idx:
                kline_data = row.get("kline_closes", [])
                if kline_data and len(kline_data) >= 2:
                    sparkline_tasks.append((x_pos, row_y, w, row_height, kline_data))
                else:
                    ax.text(x_pos + w / 2, row_y + row_height / 2, "--",
                            fontproperties=font_prop, fontsize=9,
                            ha="center", va="center", color="#AAAAAA")
                x_pos += w
                continue

            # 文字颜色
            text_color = "#333333"
            fw = font_prop

            # 年初至今列: 涨红跌绿
            if j == 4 and cell != "--":
                val = row["ytd_change_pct"]
                if val > 0:
                    text_color = "#D32F2F"
                elif val < 0:
                    text_color = "#2E7D32"

            # 股息率列: 高亮
            if j == 5:
                dv = row["dividend_yield"]
                if dv >= 6:
                    text_color = "#C62828"
                    fw = font_prop_bold
                elif dv >= 5:
                    text_color = "#E65100"
                    fw = font_prop_bold

            # 评分列: 高分高亮
            if has_score and j == 6:
                sv = row.get("eval_score", 0)
                if sv >= 85:
                    text_color = "#C62828"
                    fw = font_prop_bold
                elif sv >= 75:
                    text_color = "#E65100"
                    fw = font_prop_bold
                elif sv >= 65:
                    text_color = "#F57F17"

            # 评级列: 着色
            if has_score and j == 7:
                sv = row.get("eval_score", 0)
                if sv >= 80:
                    text_color = "#C62828"
                    fw = font_prop_bold
                elif sv >= 70:
                    text_color = "#E65100"
                elif sv >= 60:
                    text_color = "#F57F17"

            ax.text(x_pos + w / 2, row_y + row_height / 2, cell,
                    fontproperties=fw, fontsize=9.5,
                    ha="center", va="center", color=text_color)
            x_pos += w

        current_y = row_y

    # ---------- 表格外框 ----------
    total_w = sum(col_widths)
    table_bottom = current_y
    border = plt.Rectangle((0, table_bottom), total_w,
                            table_top - header_height - table_bottom + header_height,
                            facecolor="none", edgecolor="#1a2a4a", linewidth=1.5)
    ax.add_patch(border)

    ax.plot([0, total_w], [table_top - header_height, table_top - header_height],
            color="#1a2a4a", linewidth=1.5)

    # ---------- 底部说明 ----------
    footer_y = table_bottom - 0.25
    valid = [r for r in table_rows if r["dividend_yield"] > 0]
    avg_dv = sum(r["dividend_yield"] for r in valid) / len(valid) if valid else 0
    ge6 = sum(1 for r in valid if r["dividend_yield"] >= 6)
    ge5 = sum(1 for r in valid if r["dividend_yield"] >= 5)

    ytd_valid = [r for r in table_rows if r["ytd_price"] > 0]
    up_cnt = sum(1 for r in ytd_valid if r["ytd_change_pct"] > 0)
    dn_cnt = sum(1 for r in ytd_valid if r["ytd_change_pct"] < 0)

    footer_text = (f"共{len(table_rows)}只标的  |  平均股息率 {avg_dv:.2f}%  |  "
                   f"≥6%: {ge6}只  ≥5%: {ge5}只  |  "
                   f"年初至今 ↑{up_cnt}只 ↓{dn_cnt}只  |  "
                   f"涨=红色 跌=绿色  高股息=红底高亮  走势=年初至今")
    if has_score:
        scored_rows = [r for r in table_rows if r.get("eval_score", 0) > 0]
        avg_sc = sum(r["eval_score"] for r in scored_rows) / len(scored_rows) if scored_rows else 0
        ge80 = sum(1 for r in scored_rows if r["eval_score"] >= 80)
        footer_text += f"  |  平均评分 {avg_sc:.1f}  ≥80分: {ge80}只"
    ax.text(0.5, footer_y, footer_text,
            fontproperties=font_prop, fontsize=9,
            ha="center", va="center", color="#888888")

    # ---------- 第二遍：确保布局定型后再绘制sparkline ----------
    # 必须先设置subplots_adjust并draw，确保坐标变换准确
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.canvas.draw()

    # 现在坐标变换已经稳定，绘制所有sparkline
    for (sp_x, sp_y, sp_w, sp_h, sp_closes) in sparkline_tasks:
        _draw_sparkline(ax, sp_x, sp_y, sp_w, sp_h, sp_closes, fig, fig_height)

    # ---------- 保存 ----------
    # 使用 pad_inches=0 保证 figure 坐标与保存图片完全一致，不产生偏移
    fig.savefig(output_path, dpi=150, pad_inches=0,
                facecolor="#FFFFFF", edgecolor="none")
    plt.close(fig)
    print(f"🖼️  表格图片已保存至: {output_path}")


def get_stock_dividend_table():
    """获取并展示高股息标的股息率表格"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print("╔" + "═" * 96 + "╗")
    print("║" + "高股息标的股息率(TTM)排行榜".center(80) + "║")
    print("║" + f"数据来源: 腾讯财经 (qt.gtimg.cn)  |  更新时间: {now_str}".center(86) + "║")
    print("╚" + "═" * 96 + "╝")

    # ===== 批量获取实时行情(含股息率) =====
    print("\n⏳ 正在从腾讯财经获取实时行情数据...")
    codes = [item[0] for item in STOCK_LIST]

    all_data = {}
    batch_size = 30
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        raw = fetch_tencent_quotes(batch)
        parsed = parse_quotes(raw)
        all_data.update(parsed)
        if i + batch_size < len(codes):
            time.sleep(0.3)

    print(f"✅ 成功获取 {len(all_data)} 只标的实时数据")

    # ===== 获取年初至今K线(一次查询同时获取年初价格 + 走势数据) =====
    year = datetime.now().year
    print(f"\n⏳ 正在获取 {year} 年初至今K线数据(逐只查询, 请耐心等待)...")
    year_klines = fetch_year_klines(codes)
    print(f"✅ 成功获取 {len(year_klines)} 只标的年初至今K线\n")

    # ===== 整合数据 =====
    table_rows = []
    for code, expected_name in STOCK_LIST:
        if code not in all_data:
            print(f"  [跳过] {expected_name}({code}) 未获取到数据")
            continue
        info = all_data[code]

        dv_yield = info["dividend_yield"]

        # 分类: 按板块归类
        _category_map = {
            "中国广核": "电力", "中国核电": "电力", "长江电力": "电力", "华能水电": "电力",
            "国投电力": "电力", "川投能源": "电力", "内蒙华电": "电力", "浙能电力": "电力",
            "国电电力": "电力",
            "农业银行": "银行", "工商银行": "银行", "宁波银行": "银行", "招商银行": "银行",
            "中国银行": "银行", "建设银行": "银行", "交通银行": "银行", "邮储银行": "银行",
            "成都银行": "银行", "江苏银行": "银行", "北京银行": "银行", "平安银行": "银行",
            "杭州银行": "银行", "兴业银行": "银行", "光大银行": "银行", "华夏银行": "银行",
            "民生银行": "银行",
            "中国平安": "保险", "中国太保": "保险",
            "贵州茅台": "白酒", "五粮液": "白酒", "泸州老窖": "白酒", "山西汾酒": "白酒",
            "中国移动": "通讯", "中国电信": "通讯",
            "中远海控": "运输", "大秦铁路": "运输", "中谷物流": "运输", "四川成渝": "运输",
            "招商公路": "运输",
            "迈瑞医疗": "医疗器械",
            "分众传媒": "传媒",
            "伊利股份": "食品饮料", "双汇发展": "食品饮料",
            "美的集团": "家电", "格力电器": "家电", "海尔智家": "家电",
            "中国神华": "煤炭油气", "中国海油": "煤炭油气",
            "苏泊尔": "小家电",
            "云南白药": "中药", "东阿阿胶": "中药",
            "健盛集团": "服装家纺",
        }
        category = _category_map.get(info["name"], "其他")

        # 年初价格和年初至今涨跌幅
        ytd_price = 0.0
        ytd_change_pct = 0.0
        ytd_date = ""
        kline_closes = []
        if code in year_klines:
            yk = year_klines[code]
            ysp = yk["year_start"]
            ytd_price = ysp["open"]  # 用年初第一个交易日开盘价
            ytd_date = ysp["date"]
            if ytd_price > 0:
                ytd_change_pct = round((info["price"] - ytd_price) / ytd_price * 100, 2)
            kline_closes = yk["kline_closes"]  # 年初至今全部收盘价

        table_rows.append({
            "name": info["name"],
            "code": info["code"],
            "tq_code": code,
            "price": info["price"],
            "change_pct": info["change_pct"],
            "turnover_rate": info["turnover_rate"],
            "circ_mv": info["circ_mv"],
            "pe": info["pe_dynamic"],
            "pb": info["pb"],
            "total_mv": info["total_mv"],
            "dividend_yield": dv_yield,
            "high_52w": info["high_52w"],
            "low_52w": info["low_52w"],
            "category": category,
            "ytd_price": ytd_price,
            "ytd_change_pct": ytd_change_pct,
            "kline_closes": kline_closes,
        })

    # 按板块分组，板块内按股息率降序排列
    # 1. 计算每个板块的平均股息率，用于板块间排序
    from collections import defaultdict as _defaultdict
    _cat_rows = _defaultdict(list)
    for row in table_rows:
        _cat_rows[row["category"]].append(row)
    # 2. 板块按平均股息率降序
    _cat_order = sorted(_cat_rows.keys(),
                        key=lambda c: sum(r["dividend_yield"] for r in _cat_rows[c]) / len(_cat_rows[c]),
                        reverse=True)
    # 3. 板块内按股息率降序
    sorted_rows = []
    for cat in _cat_order:
        rows_in_cat = sorted(_cat_rows[cat], key=lambda x: x["dividend_yield"], reverse=True)
        sorted_rows.extend(rows_in_cat)
    table_rows = sorted_rows

    # ===== 批量评估(评分) =====
    print(f"⏳ 正在进行综合评分(逐只评估)...")
    try:
        from dividend_evaluator import DividendEvaluator
        for row in table_rows:
            try:
                ev = DividendEvaluator()
                # 直接注入已有数据，避免重复请求行情
                ev.stock_data = {
                    "name": row["name"], "code": row["code"],
                    "price": row["price"], "pe_dynamic": row["pe"], "pb": row["pb"],
                    "total_mv": row["total_mv"], "circ_mv": row["circ_mv"],
                    "dividend_yield": row["dividend_yield"],
                    "high_52w": row["high_52w"], "low_52w": row["low_52w"],
                    "turnover_rate": row.get("turnover_rate", 0.5),
                }
                ev.ytd_data = {"open": row["ytd_price"]} if row["ytd_price"] > 0 else {}
                code6 = row["tq_code"][2:]
                ev.fetch_dividend_history(code6, quiet=True)
                # 注入同业数据
                for r2 in table_rows:
                    ev.peer_data[r2["tq_code"]] = {
                        "name": r2["name"], "code": r2["code"],
                        "dividend_yield": r2["dividend_yield"],
                        "pe_dynamic": r2["pe"], "pb": r2["pb"],
                    }
                # 执行六维评分
                funcs = [
                    ("dividend_yield", ev.score_dividend_yield),
                    ("valuation_safety", ev.score_valuation_safety),
                    ("dividend_continuity", ev.score_dividend_continuity),
                    ("fundamentals", ev.score_fundamentals),
                    ("growth_potential", ev.score_growth_potential),
                    ("market_performance", ev.score_market_performance),
                ]
                from dividend_evaluator import SCORE_WEIGHTS, RATING_THRESHOLDS
                for key, fn in funcs:
                    s, d = fn()
                    ev.scores[key] = {"score": s, "detail": d}
                total = round(sum(ev.scores[k]["score"] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS), 1)
                rating_str = "--"
                for th, stars, level, desc in RATING_THRESHOLDS:
                    if total >= th:
                        rating_str = f"{level}"
                        break
                row["eval_score"] = total
                row["eval_rating"] = rating_str
            except Exception as e:
                row["eval_score"] = 0
                row["eval_rating"] = "--"
        scored = [r for r in table_rows if r.get("eval_score", 0) > 0]
        print(f"✅ 成功评分 {len(scored)} 只标的")
    except ImportError:
        print(f"⚠️ 未找到评估模块，跳过评分")

    # ===== 打印表格(按板块分组) =====
    has_score_col = any(r.get("eval_score", 0) > 0 for r in table_rows)
    if has_score_col:
        header = (f"{'股票名称':<10} │ {'代码':<8} │ {'现价':>7} │ {'年初价':>7} │ {'年初至今':>8} │ "
                  f"{'股息率%':>7} │ {'评分':>5} │ {'评级':<6} │ {'PE(动)':>7} │ {'PB':>6} │ {'总市值(亿)':>10}")
        sep = "─" * 130
    else:
        header = (f"{'股票名称':<10} │ {'代码':<8} │ {'现价':>7} │ {'年初价':>7} │ {'年初至今':>8} │ "
                  f"{'股息率%':>7} │ {'PE(动)':>7} │ {'PB':>6} │ {'总市值(亿)':>10}")
        sep = "─" * 104
    print(sep)
    print(header)
    print(sep)

    from collections import OrderedDict as _OD2
    _cat_groups2 = _OD2()
    for row in table_rows:
        cat = row["category"]
        if cat not in _cat_groups2:
            _cat_groups2[cat] = []
        _cat_groups2[cat].append(row)

    rank = 0
    for cat, rows_in_cat in _cat_groups2.items():
        cat_avg_dv = sum(r["dividend_yield"] for r in rows_in_cat) / len(rows_in_cat)
        print(f"  ▎{cat} ({len(rows_in_cat)}只, 均值 {cat_avg_dv:.2f}%)")
        for row in rows_in_cat:
            rank += 1
            mv_str = f"{row['total_mv']:.0f}" if row["total_mv"] >= 1 else f"{row['total_mv']:.2f}"
            dv_str = f"{row['dividend_yield']:.2f}" if row["dividend_yield"] > 0 else "  --"
            ytd_price_str = f"{row['ytd_price']:.2f}" if row["ytd_price"] > 0 else "   --"
            ytd_chg_str = f"{row['ytd_change_pct']:+.2f}%" if row["ytd_price"] > 0 else "    --"

            # 高亮高股息行
            marker = ""
            if row["dividend_yield"] >= 6:
                marker = " 🔥"
            elif row["dividend_yield"] >= 5:
                marker = " ⭐"

            # 年初至今涨跌幅颜色标记
            ytd_marker = ""
            if row["ytd_change_pct"] >= 10:
                ytd_marker = "📈"
            elif row["ytd_change_pct"] <= -10:
                ytd_marker = "📉"

            print(f"{row['name']:<10} │ {row['code']:<8} │ {row['price']:>7.2f} │ {ytd_price_str:>7} │ {ytd_chg_str:>7}{ytd_marker:<1}│ "
                  f"{dv_str:>7}{marker:<3}│ ", end="")
            if has_score_col:
                sc = row.get("eval_score", 0)
                sr = row.get("eval_rating", "--")
                sc_str = f"{sc:.1f}" if sc > 0 else "  --"
                print(f"{sc_str:>5} │ {sr:<6} │ ", end="")
            print(f"{row['pe']:>7.2f} │ {row['pb']:>6.2f} │ {mv_str:>10}")

    print(sep)

    # ===== 统计摘要 =====
    valid_rows = [r for r in table_rows if r["dividend_yield"] > 0]
    ytd_rows = [r for r in table_rows if r["ytd_price"] > 0]
    if valid_rows:
        avg_dv = sum(r["dividend_yield"] for r in valid_rows) / len(valid_rows)
        max_dv = valid_rows[0]
        min_dv = valid_rows[-1]

        # 按类型统计
        cat_stats = {}
        for r in valid_rows:
            cat = r["category"]
            if cat not in cat_stats:
                cat_stats[cat] = {"dv": [], "ytd": []}
            cat_stats[cat]["dv"].append(r["dividend_yield"])
            if r["ytd_price"] > 0:
                cat_stats[cat]["ytd"].append(r["ytd_change_pct"])

        print(f"\n📊 统计摘要 (共 {len(table_rows)} 只标的):")
        print(f"   {'整体平均股息率:':<20} {avg_dv:.2f}%")
        print(f"   {'最高股息率:':<20} {max_dv['name']} ({max_dv['dividend_yield']:.2f}%)")
        print(f"   {'最低股息率:':<20} {min_dv['name']} ({min_dv['dividend_yield']:.2f}%)")
        print(f"   {'股息率 ≥ 6% :':<20} {sum(1 for r in valid_rows if r['dividend_yield'] >= 6)} 只")
        print(f"   {'股息率 ≥ 5% :':<20} {sum(1 for r in valid_rows if r['dividend_yield'] >= 5)} 只")
        print(f"   {'股息率 ≥ 4% :':<20} {sum(1 for r in valid_rows if r['dividend_yield'] >= 4)} 只")

        if ytd_rows:
            avg_ytd = sum(r["ytd_change_pct"] for r in ytd_rows) / len(ytd_rows)
            best_ytd = max(ytd_rows, key=lambda r: r["ytd_change_pct"])
            worst_ytd = min(ytd_rows, key=lambda r: r["ytd_change_pct"])
            print(f"\n📅 {year}年初至今涨跌幅统计:")
            print(f"   {'平均涨跌幅:':<20} {avg_ytd:+.2f}%")
            print(f"   {'涨幅最大:':<20} {best_ytd['name']} ({best_ytd['ytd_change_pct']:+.2f}%)")
            print(f"   {'跌幅最大:':<20} {worst_ytd['name']} ({worst_ytd['ytd_change_pct']:+.2f}%)")
            print(f"   {'年初至今上涨:':<20} {sum(1 for r in ytd_rows if r['ytd_change_pct'] > 0)} 只")
            print(f"   {'年初至今下跌:':<20} {sum(1 for r in ytd_rows if r['ytd_change_pct'] < 0)} 只")

        print(f"\n📈 分类统计:")
        for cat in sorted(cat_stats.keys(), key=lambda c: -sum(cat_stats[c]["dv"])/len(cat_stats[c]["dv"])):
            if cat in cat_stats:
                dvs = cat_stats[cat]["dv"]
                ytds = cat_stats[cat]["ytd"]
                ytd_str = f"  年初至今平均: {sum(ytds)/len(ytds):+.2f}%" if ytds else ""
                print(f"   {cat:<16} 平均股息率: {sum(dvs)/len(dvs):.2f}%  "
                      f"(最高 {max(dvs):.2f}%, 最低 {min(dvs):.2f}%, {len(dvs)}只){ytd_str}")

    # ===== 保存CSV =====
    csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_dividend.csv")
    try:
        with open(csv_file, "w", encoding="utf-8-sig") as f:
            f.write(f"排名,股票名称,股票代码,类型,现价(元),年初价格(元),年初至今涨跌幅%,"
                    f"股息率%(TTM),综合评分,评级,"
                    f"市盈率PE(动态),市净率PB,总市值(亿元),52周最高,52周最低\n")
            for i, row in enumerate(table_rows, 1):
                ytd_p = f"{row['ytd_price']:.2f}" if row['ytd_price'] > 0 else ""
                ytd_c = f"{row['ytd_change_pct']:.2f}" if row['ytd_price'] > 0 else ""
                sc = row.get("eval_score", 0)
                sr = row.get("eval_rating", "")
                sc_str = f"{sc:.1f}" if sc > 0 else ""
                f.write(f"{i},{row['name']},{row['code']},{row['category']},"
                        f"{row['price']:.2f},{ytd_p},{ytd_c},"
                        f"{row['dividend_yield']:.2f},{sc_str},{sr},"
                        f"{row['pe']:.2f},"
                        f"{row['pb']:.2f},{row['total_mv']:.2f},"
                        f"{row['high_52w']:.2f},{row['low_52w']:.2f}\n")
        print(f"\n💾 数据已保存至: {csv_file}")
    except Exception as e:
        print(f"\n[警告] CSV保存失败: {e}")

    # ===== 生成表格图片 =====
    img_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_dividend.png")
    print(f"\n⏳ 正在生成表格图片...")
    try:
        generate_table_image(table_rows, img_file)
    except Exception as e:
        print(f"[警告] 图片生成失败: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n📌 说明:")
    print(f"   • 股息率(TTM) = 近12个月累计每股分红 ÷ 当前股价 × 100%")
    print(f"   • 年初价格 = {year}年第一个交易日开盘价 (前复权)")
    print(f"   • 年初至今涨跌幅 = (现价 - 年初价格) / 年初价格 × 100%")
    print(f"   • 数据全部来自腾讯财经接口 (qt.gtimg.cn / web.ifzq.gtimg.cn)")
    print(f"   • 🔥 = 股息率≥6%   ⭐ = 股息率≥5%   📈 = 年涨≥10%   📉 = 年跌≥10%")


if __name__ == "__main__":
    get_stock_dividend_table()
