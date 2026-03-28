#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国内上市银行股息率查询工具
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

# ===================== 国内A股上市银行完整列表 =====================
BANK_STOCKS = [
    # 六大国有银行
    ("sh601398", "工商银行"),
    ("sh601939", "建设银行"),
    ("sh601288", "农业银行"),
    ("sh601988", "中国银行"),
    ("sh601328", "交通银行"),
    ("sh601658", "邮储银行"),
    # 股份制商业银行
    ("sh600036", "招商银行"),
    ("sh600016", "民生银行"),
    ("sh600000", "浦发银行"),
    ("sz000001", "平安银行"),
    ("sh601166", "兴业银行"),
    ("sz002142", "宁波银行"),
    ("sh601818", "光大银行"),
    ("sh600015", "华夏银行"),
    ("sh601998", "中信银行"),
    # 城商行 & 农商行
    ("sh600919", "江苏银行"),
    ("sh601169", "北京银行"),
    ("sh600926", "杭州银行"),
    ("sh601009", "南京银行"),
    ("sh601916", "浙商银行"),
    ("sh601838", "成都银行"),
    ("sh601577", "长沙银行"),
    ("sh601963", "重庆银行"),
    ("sh601997", "贵阳银行"),
    ("sz002948", "青岛银行"),
    ("sh601187", "厦门银行"),
    ("sh600928", "西安银行"),
    ("sh601665", "齐鲁银行"),
    ("sz001227", "兰州银行"),
    ("sh601077", "渝农商行"),
    ("sh601825", "沪农商行"),
    ("sh601528", "瑞丰银行"),
    ("sh601860", "紫金银行"),
    ("sh600908", "无锡银行"),
    ("sh601128", "常熟银行"),
    ("sh603323", "苏农银行"),
    ("sz002839", "张家港行"),
    ("sz002807", "江阴银行"),
    ("sz002936", "郑州银行"),
    ("sz002966", "苏州银行"),
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


def fetch_year_start_price(codes):
    """
    通过腾讯财经日K线接口获取年初第一个交易日的开盘价
    接口: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
    参数: param=代码,day,开始日期,结束日期,数量,qfq
    K线格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
    """
    year = datetime.now().year
    start_date = f"{year}-01-01"
    end_date = f"{year}-01-10"  # 取前10天足以覆盖第一个交易日
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
                   f"?param={code},day,{start_date},{end_date},5,qfq")
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                stock_data = data["data"].get(code, {})
                klines = stock_data.get("qfqday", []) or stock_data.get("day", [])
                if klines and len(klines) > 0:
                    # 第一个交易日: [日期, 开盘, 收盘, 最高, 最低, 成交量]
                    first_day = klines[0]
                    results[code] = {
                        "date": first_day[0],
                        "open": float(first_day[1]),   # 年初开盘价
                        "close": float(first_day[2]),   # 年初收盘价
                    }
        except Exception:
            pass
        time.sleep(0.15)  # 控制请求频率
    return results


def fetch_recent_klines(codes, days=40):
    """
    获取最近N天的日K线收盘价数据，用于绘制走势缩略图
    返回: {code: [close_price_1, close_price_2, ...], ...}
    """
    from datetime import timedelta
    today = datetime.now()
    # 多取一些日历天数以确保覆盖足够交易日
    start_date = (today - timedelta(days=int(days * 1.8))).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.qq.com/",
    }
    results = {}
    for code in codes:
        try:
            url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                   f"?param={code},day,{start_date},{end_date},{days + 10},qfq")
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                stock_data = data["data"].get(code, {})
                klines = stock_data.get("qfqday", []) or stock_data.get("day", [])
                if klines:
                    # 取最后 days 根K线的收盘价
                    closes = [float(k[2]) for k in klines[-days:]]
                    results[code] = closes
        except Exception:
            pass
        time.sleep(0.15)
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
    将银行股息率数据生成一张精美的表格图片
    table_rows: 已按股息率降序排好的数据列表 (每个 row 需含 'kline_closes' 字段)
    output_path: 图片保存路径
    """
    font_prop = _find_cjk_font()
    font_prop_bold = font_prop.copy()
    font_prop_bold.set_weight("bold")

    year = datetime.now().year
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---------- 准备表格数据 ----------
    col_headers = ["排名", "银行", "代码", "现价", "年初价",
                   "年初至今", "股息率(TTM)", "PE", "PB", "市值(亿)", "走势(40日)", "类型"]
    n_cols = len(col_headers)
    n_rows = len(table_rows)

    # 走势列索引
    sparkline_col_idx = 10

    cell_texts = []
    for i, row in enumerate(table_rows, 1):
        ytd_price_str = f"{row['ytd_price']:.2f}" if row["ytd_price"] > 0 else "--"
        ytd_chg_str = f"{row['ytd_change_pct']:+.2f}%" if row["ytd_price"] > 0 else "--"
        dv_str = f"{row['dividend_yield']:.2f}%"
        mv_str = f"{row['total_mv']:.0f}" if row["total_mv"] >= 1 else f"{row['total_mv']:.2f}"

        cell_texts.append([
            str(i),
            row["name"],
            row["code"],
            f"{row['price']:.2f}",
            ytd_price_str,
            ytd_chg_str,
            dv_str,
            f"{row['pe']:.2f}",
            f"{row['pb']:.2f}",
            mv_str,
            "",  # 走势列占位，由 sparkline 绘制
            row["category"],
        ])

    # ---------- 颜色方案 ----------
    header_bg = "#1a2a4a"
    header_fg = "#FFFFFF"
    row_bg_even = "#F8FAFD"
    row_bg_odd = "#FFFFFF"
    grid_color = "#D0D8E8"

    # ---------- 计算尺寸 ----------
    # 12列: 排名, 银行, 代码, 现价, 年初价, 年初至今, 股息率, PE, PB, 市值, 走势, 类型
    col_widths = [0.035, 0.075, 0.075, 0.06, 0.06, 0.085, 0.10, 0.06, 0.06, 0.075, 0.13, 0.085]
    fig_width = 18
    row_height = 0.42
    header_height = 0.48
    title_height = 1.0
    footer_height = 0.6
    table_height = header_height + n_rows * row_height
    fig_height = title_height + table_height + footer_height

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, fig_height)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # ---------- 标题区域 ----------
    title_y = fig_height - title_height * 0.45
    ax.text(0.5, title_y, f"国内上市银行股息率(TTM)排行榜",
            fontproperties=font_prop_bold, fontsize=20,
            ha="center", va="center", color="#1a2a4a")
    ax.text(0.5, title_y - 0.35,
            f"数据来源: 腾讯财经  |  {now_str}  |  按股息率从高到低排序  |  含近40日走势",
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

    for i, (row, cells) in enumerate(zip(table_rows, cell_texts)):
        row_y = table_top - header_height - (i + 1) * row_height
        bg = row_bg_even if i % 2 == 0 else row_bg_odd

        x_pos = 0.0
        for j, (cell, w) in enumerate(zip(cells, col_widths)):
            cell_bg = bg

            # 股息率列特殊着色
            if j == 6:
                dv = row["dividend_yield"]
                if dv >= 6:
                    cell_bg = "#FDEAEA"
                elif dv >= 5:
                    cell_bg = "#FFF3E0"
                elif dv >= 4:
                    cell_bg = "#FFFDE7"
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
            if j == 5 and cell != "--":
                val = row["ytd_change_pct"]
                if val > 0:
                    text_color = "#D32F2F"
                elif val < 0:
                    text_color = "#2E7D32"

            # 股息率列: 高亮
            if j == 6:
                dv = row["dividend_yield"]
                if dv >= 6:
                    text_color = "#C62828"
                    fw = font_prop_bold
                elif dv >= 5:
                    text_color = "#E65100"
                    fw = font_prop_bold

            # 排名列前3高亮
            if j == 0 and i < 3:
                text_color = "#C62828"
                fw = font_prop_bold

            ax.text(x_pos + w / 2, row_y + row_height / 2, cell,
                    fontproperties=fw, fontsize=9.5,
                    ha="center", va="center", color=text_color)
            x_pos += w

    # ---------- 表格外框 ----------
    total_w = sum(col_widths)
    table_bottom = table_top - header_height - n_rows * row_height
    border = plt.Rectangle((0, table_bottom), total_w,
                            header_height + n_rows * row_height,
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

    footer_text = (f"共{len(table_rows)}只银行  |  平均股息率 {avg_dv:.2f}%  |  "
                   f"≥6%: {ge6}只  ≥5%: {ge5}只  |  "
                   f"年初至今 ↑{up_cnt}只 ↓{dn_cnt}只  |  "
                   f"涨=红色 跌=绿色  高股息=红底高亮  走势=近40交易日")
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


def get_bank_dividend_table():
    """获取并展示银行股股息率表格"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print("╔" + "═" * 96 + "╗")
    print("║" + "国内上市银行股息率(TTM)排行榜".center(80) + "║")
    print("║" + f"数据来源: 腾讯财经 (qt.gtimg.cn)  |  更新时间: {now_str}".center(86) + "║")
    print("╚" + "═" * 96 + "╝")

    # ===== 批量获取实时行情(含股息率) =====
    print("\n⏳ 正在从腾讯财经获取实时行情数据...")
    codes = [item[0] for item in BANK_STOCKS]

    all_data = {}
    batch_size = 30
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        raw = fetch_tencent_quotes(batch)
        parsed = parse_quotes(raw)
        all_data.update(parsed)
        if i + batch_size < len(codes):
            time.sleep(0.3)

    print(f"✅ 成功获取 {len(all_data)} 只银行股实时数据")

    # ===== 获取年初价格 =====
    year = datetime.now().year
    print(f"\n⏳ 正在获取 {year} 年初价格数据(逐只查询, 请耐心等待)...")
    year_start_prices = fetch_year_start_price(codes)
    print(f"✅ 成功获取 {len(year_start_prices)} 只银行年初价格")

    # ===== 获取最近40天K线(走势图) =====
    print(f"\n⏳ 正在获取最近40天K线数据(逐只查询, 用于走势图)...")
    recent_klines = fetch_recent_klines(codes, days=40)
    print(f"✅ 成功获取 {len(recent_klines)} 只银行近40日K线\n")

    # ===== 整合数据 =====
    table_rows = []
    for code, expected_name in BANK_STOCKS:
        if code not in all_data:
            print(f"  [跳过] {expected_name}({code}) 未获取到数据")
            continue
        info = all_data[code]

        dv_yield = info["dividend_yield"]

        # 分类: 国有大行 / 股份行 / 城商行&农商行
        category = "城商行&农商行"
        big6 = ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行", "邮储银行"]
        share_banks = ["招商银行", "民生银行", "浦发银行", "平安银行", "兴业银行",
                       "宁波银行", "光大银行", "华夏银行", "中信银行"]
        if info["name"] in big6:
            category = "国有大行"
        elif info["name"] in share_banks:
            category = "股份制银行"

        # 年初价格和年初至今涨跌幅
        ytd_price = 0.0
        ytd_change_pct = 0.0
        ytd_date = ""
        if code in year_start_prices:
            ysp = year_start_prices[code]
            ytd_price = ysp["open"]  # 用年初第一个交易日开盘价
            ytd_date = ysp["date"]
            if ytd_price > 0:
                ytd_change_pct = round((info["price"] - ytd_price) / ytd_price * 100, 2)

        # 最近40天K线收盘价
        kline_closes = recent_klines.get(code, [])

        table_rows.append({
            "name": info["name"],
            "code": info["code"],
            "tq_code": code,
            "price": info["price"],
            "change_pct": info["change_pct"],
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

    # 按股息率降序排列
    table_rows.sort(key=lambda x: x["dividend_yield"], reverse=True)

    # ===== 打印表格 =====
    header = (f"{'排名':>4} │ {'银行名称':<10} │ {'代码':<8} │ {'现价':>7} │ {'年初价':>7} │ {'年初至今':>8} │ "
              f"{'股息率%':>7} │ {'PE(动)':>7} │ {'PB':>6} │ {'总市值(亿)':>10} │ {'类型':<12}")
    sep = "─" * 126
    print(sep)
    print(header)
    print(sep)

    for i, row in enumerate(table_rows, 1):
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

        print(f"{i:>4} │ {row['name']:<10} │ {row['code']:<8} │ {row['price']:>7.2f} │ {ytd_price_str:>7} │ {ytd_chg_str:>7}{ytd_marker:<1}│ "
              f"{dv_str:>7}{marker:<3}│ {row['pe']:>7.2f} │ {row['pb']:>6.2f} │ {mv_str:>10} │ {row['category']:<12}")

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

        print(f"\n📊 统计摘要 (共 {len(table_rows)} 只银行股):")
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
        for cat in ["国有大行", "股份制银行", "城商行&农商行"]:
            if cat in cat_stats:
                dvs = cat_stats[cat]["dv"]
                ytds = cat_stats[cat]["ytd"]
                ytd_str = f"  年初至今平均: {sum(ytds)/len(ytds):+.2f}%" if ytds else ""
                print(f"   {cat:<16} 平均股息率: {sum(dvs)/len(dvs):.2f}%  "
                      f"(最高 {max(dvs):.2f}%, 最低 {min(dvs):.2f}%, {len(dvs)}只){ytd_str}")

    # ===== 保存CSV =====
    csv_file = "/Users/leking/Desktop/stock/bank_dividend.csv"
    try:
        with open(csv_file, "w", encoding="utf-8-sig") as f:
            f.write(f"排名,银行名称,股票代码,类型,现价(元),年初价格(元),年初至今涨跌幅%,"
                    f"股息率%(TTM),市盈率PE(动态),市净率PB,总市值(亿元),52周最高,52周最低\n")
            for i, row in enumerate(table_rows, 1):
                ytd_p = f"{row['ytd_price']:.2f}" if row['ytd_price'] > 0 else ""
                ytd_c = f"{row['ytd_change_pct']:.2f}" if row['ytd_price'] > 0 else ""
                f.write(f"{i},{row['name']},{row['code']},{row['category']},"
                        f"{row['price']:.2f},{ytd_p},{ytd_c},"
                        f"{row['dividend_yield']:.2f},{row['pe']:.2f},"
                        f"{row['pb']:.2f},{row['total_mv']:.2f},"
                        f"{row['high_52w']:.2f},{row['low_52w']:.2f}\n")
        print(f"\n💾 数据已保存至: {csv_file}")
    except Exception as e:
        print(f"\n[警告] CSV保存失败: {e}")

    # ===== 生成表格图片 =====
    img_file = "/Users/leking/Desktop/stock/bank_dividend.png"
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
    get_bank_dividend_table()
