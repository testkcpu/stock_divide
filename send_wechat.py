#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信机器人消息发送工具
用于发送股息分析结果和图片
"""

import requests
import json
import os
import base64
import hashlib
from datetime import datetime

# 企业微信机器人Webhook地址
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=a986619b-3ca0-4282-a354-ad181a22bb57"


def send_text_message(content):
    """发送文本消息"""
    data = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    response = requests.post(WEBHOOK_URL, json=data, timeout=30)
    return response.json()


def send_markdown_message(content):
    """发送Markdown消息"""
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    response = requests.post(WEBHOOK_URL, json=data, timeout=30)
    return response.json()


def send_image_message(image_path):
    """发送图片消息"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # 计算图片的base64编码和md5值
    base64_data = base64.b64encode(image_data).decode('utf-8')
    md5_value = hashlib.md5(image_data).hexdigest()
    
    data = {
        "msgtype": "image",
        "image": {
            "base64": base64_data,
            "md5": md5_value
        }
    }
    response = requests.post(WEBHOOK_URL, json=data, timeout=30)
    return response.json()


def send_news_message(title, description, url, picurl=""):
    """发送图文消息"""
    data = {
        "msgtype": "news",
        "news": {
            "articles": [
                {
                    "title": title,
                    "description": description,
                    "url": url,
                    "picurl": picurl
                }
            ]
        }
    }
    response = requests.post(WEBHOOK_URL, json=data, timeout=30)
    return response.json()


def generate_summary_from_csv(csv_path):
    """从CSV文件生成汇总信息"""
    if not os.path.exists(csv_path):
        return "未找到数据文件"
    
    try:
        import csv
        rows = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        if not rows:
            return "数据为空"
        
        # 计算统计数据
        total = len(rows)
        dividend_rates = [float(r['股息率%(TTM)']) for r in rows if r.get('股息率%(TTM)')]
        avg_dv = sum(dividend_rates) / len(dividend_rates) if dividend_rates else 0
        max_dv = max(dividend_rates) if dividend_rates else 0
        min_dv = min(dividend_rates) if dividend_rates else 0
        
        # 统计各档位
        ge_6 = sum(1 for d in dividend_rates if d >= 6)
        ge_5 = sum(1 for d in dividend_rates if d >= 5)
        ge_4 = sum(1 for d in dividend_rates if d >= 4)
        
        # 获取最高股息率股票
        max_stock = max(rows, key=lambda r: float(r.get('股息率%(TTM)', 0) or 0))
        
        # 获取涨幅最大股票
        ytd_changes = [(r, float(r.get('年初至今涨跌幅%', 0) or 0)) for r in rows if r.get('年初至今涨跌幅%')]
        if ytd_changes:
            best_ytd = max(ytd_changes, key=lambda x: x[1])
            worst_ytd = min(ytd_changes, key=lambda x: x[1])
        
        # 生成年月日
        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M")
        
        # 生成汇总文本
        summary = f"📊 **高股息标的股息率日报** ({date_str} {time_str})\n\n"
        summary += f"**统计摘要** (共 {total} 只标的):\n"
        summary += f"> 📈 整体平均股息率: **{avg_dv:.2f}%**\n"
        summary += f"> 🔥 最高股息率: **{max_stock['股票名称']}** ({max_dv:.2f}%)\n"
        summary += f"> 📉 最低股息率: **{min_dv:.2f}%**\n\n"
        
        summary += f"**股息率分布**:\n"
        summary += f"> ✅ ≥ 6%: **{ge_6}** 只\n"
        summary += f"> ⭐ ≥ 5%: **{ge_5}** 只\n"
        summary += f"> 📊 ≥ 4%: **{ge_4}** 只\n\n"
        
        if ytd_changes:
            summary += f"**年初至今表现**:\n"
            summary += f"> 🚀 涨幅最大: **{best_ytd[0]['股票名称']}** ({best_ytd[1]:+.2f}%)\n"
            summary += f"> 📉 跌幅最大: **{worst_ytd[0]['股票名称']}** ({worst_ytd[1]:+.2f}%)\n\n"
        
        # 显示Top 5高股息率股票
        top5 = sorted(rows, key=lambda r: float(r.get('股息率%(TTM)', 0) or 0), reverse=True)[:5]
        summary += f"**🏆 Top 5 高股息率标的**:\n"
        for i, r in enumerate(top5, 1):
            name = r['股票名称']
            code = r['股票代码']
            dv = float(r.get('股息率%(TTM)', 0) or 0)
            price = float(r.get('现价(元)', 0) or 0)
            ytd = float(r.get('年初至今涨跌幅%', 0) or 0)
            summary += f"> {i}. **{name}**({code}) | 股息率:{dv:.2f}% | 现价:{price:.2f}元 | 年涨跌:{ytd:+.2f}%\n"
        
        return summary
    except Exception as e:
        return f"生成汇总信息失败: {e}"


def main():
    """主函数：执行分析并发送结果"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 执行股息分析脚本
    print("🚀 正在执行股息分析...")
    import subprocess
    result = subprocess.run(
        ['python3', os.path.join(script_dir, 'bank_dividend.py')],
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    print(result.stdout)
    if result.stderr:
        print(f"警告: {result.stderr}")
    
    # 2. 生成并发送汇总信息
    csv_path = os.path.join(script_dir, 'bank_dividend.csv')
    summary = generate_summary_from_csv(csv_path)
    
    print("\n📤 正在发送汇总信息...")
    send_markdown_message(summary)
    
    # 3. 发送图片
    img_path = os.path.join(script_dir, 'bank_dividend.png')
    if os.path.exists(img_path):
        print("📸 正在发送分析图表...")
        send_image_message(img_path)
        print("✅ 发送完成!")
    else:
        print(f"⚠️ 图片文件不存在: {img_path}")
    
    return summary


if __name__ == "__main__":
    main()
