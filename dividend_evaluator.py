#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股息投资综合评估系统 - 核心评估引擎
===================================
对A股标的进行多维度股息投资评分，输出结论性报告。

评估维度(6维):
  1. 股息收益 (25%)   2. 估值安全边际 (20%)   3. 分红持续性 (15%)
  4. 基本面稳健度 (20%)   5. 成长潜力 (10%)   6. 市场表现 (10%)
"""

import requests
import re
import time
from datetime import datetime
from bank_dividend import (
    BANK_STOCKS, fetch_tencent_quotes, parse_quotes, fetch_year_start_price,
)

SCORE_WEIGHTS = {
    "dividend_yield": 0.25, "valuation_safety": 0.20,
    "dividend_continuity": 0.15, "fundamentals": 0.20,
    "growth_potential": 0.10, "market_performance": 0.10,
}

RATING_THRESHOLDS = [
    (90, "⭐⭐⭐⭐⭐", "强烈推荐", "极佳的高股息投资标的"),
    (80, "⭐⭐⭐⭐☆", "推荐", "优质的股息投资选择"),
    (70, "⭐⭐⭐⭐", "较好", "适合稳健型股息投资"),
    (60, "⭐⭐⭐☆", "一般", "股息投资价值中等"),
    (50, "⭐⭐⭐", "谨慎", "股息投资吸引力有限"),
    (40, "⭐⭐☆", "偏弱", "不太适合股息投资策略"),
    (0,  "⭐⭐", "不推荐", "股息投资价值较低"),
]

BENCHMARKS = {
    "risk_free_rate": 1.5, "deposit_rate_3y": 1.50,
}


class DividendEvaluator:
    """股息投资综合评估器"""

    def __init__(self):
        self.stock_data = None
        self.ytd_data = None
        self.dividend_history = None
        self.peer_data = {}
        self.scores = {}
        self.total_score = 0
        self.rating = self.rating_desc = ""

    # ==================== 数据获取 ====================
    def fetch_realtime_data(self, stock_code):
        print(f"\n⏳ 获取实时行情...")
        raw = fetch_tencent_quotes([stock_code])
        parsed = parse_quotes(raw)
        if stock_code not in parsed:
            raise ValueError(f"无法获取 {stock_code} 的行情数据")
        self.stock_data = parsed[stock_code]
        print(f"✅ {self.stock_data['name']}({self.stock_data['code']}) 现价:{self.stock_data['price']:.2f}")
        print(f"⏳ 获取年初价格...")
        ytd = fetch_year_start_price([stock_code])
        self.ytd_data = ytd.get(stock_code, {})
        if self.ytd_data:
            print(f"✅ 年初价: {self.ytd_data['open']:.2f}元")
        return self.stock_data

    def fetch_dividend_history(self, code6, quiet=False):
        if not quiet:
            print(f"⏳ 获取历史分红数据...")
        url = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
               f"reportName=RPT_SHAREBONUS_DET&columns=ALL"
               f"&quoteColumns=&filter=(SECURITY_CODE%3D%22{code6}%22)"
               f"&pageNumber=1&pageSize=50&sortTypes=-1&sortColumns=EX_DIVIDEND_DATE"
               f"&source=WEB&client=WEB")
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()
            if data.get("success") and data.get("result") and data["result"].get("data"):
                records = data["result"]["data"]
                self.dividend_history = []
                for r in records:
                    try:
                        cash = r.get("PRETAX_BONUS_RMB")
                        if cash is None or cash <= 0:
                            continue
                        plan_date = r.get("PLAN_NOTICE_DATE", "")
                        ex_date = r.get("EX_DIVIDEND_DATE", "")
                        year = (plan_date[:4] if plan_date else ex_date[:4]) if (plan_date or ex_date) else ""
                        assign_ratio = r.get("ASSIGN_TRANSFER_RATIO", 0) or 0
                        self.dividend_history.append({
                            "year": year,
                            "cash_per_share": float(cash) / 10.0,
                            "ex_date": ex_date[:10] if ex_date else "",
                            "payout_ratio": float(assign_ratio) if assign_ratio else 0,
                        })
                    except (TypeError, ValueError, KeyError):
                        continue
                if not quiet:
                    print(f"✅ 获取到 {len(self.dividend_history)} 条分红记录")
            else:
                self.dividend_history = []
                if not quiet:
                    print(f"⚠️ 未获取到分红历史")
        except Exception as e:
            self.dividend_history = []
            if not quiet:
                print(f"⚠️ 获取分红历史失败: {e}")
        return self.dividend_history

    def fetch_peer_data(self, category):
        print(f"⏳ 获取同业对比数据...")
        codes = [item[0] for item in BANK_STOCKS]
        raw = fetch_tencent_quotes(codes)
        all_parsed = parse_quotes(raw)
        for code, name in BANK_STOCKS:
            if code in all_parsed:
                info = all_parsed[code]
                self.peer_data[code] = {**info, "category": self._get_category(info["name"])}
        print(f"✅ 获取到 {len(self.peer_data)} 只银行数据")
        return self.peer_data

    def _get_category(self, name):
        big6 = ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行", "邮储银行"]
        share = ["招商银行", "民生银行", "浦发银行", "平安银行", "兴业银行",
                 "宁波银行", "光大银行", "华夏银行", "中信银行"]
        return "国有大行" if name in big6 else ("股份制银行" if name in share else "城商行&农商行")

    # ==================== 六维评分 ====================
    def score_dividend_yield(self):
        dy = self.stock_data["dividend_yield"]
        if dy >= 8: base = 95 + min((dy - 8) * 2.5, 5)
        elif dy >= 7: base = 85 + (dy - 7) * 10
        elif dy >= 6: base = 75 + (dy - 6) * 10
        elif dy >= 5: base = 65 + (dy - 5) * 10
        elif dy >= 4: base = 55 + (dy - 4) * 10
        elif dy >= 3: base = 40 + (dy - 3) * 15
        elif dy >= 2: base = 25 + (dy - 2) * 15
        else: base = max(10, dy / 2 * 25)
        rank_bonus = 0
        if self.peer_data:
            all_dy = sorted([v["dividend_yield"] for v in self.peer_data.values()], reverse=True)
            if all_dy:
                rank = next((i for i, d in enumerate(all_dy) if d <= dy), len(all_dy))
                pct = rank / len(all_dy)
                rank_bonus = 5 if pct <= 0.05 else (3 if pct <= 0.10 else (1 if pct <= 0.20 else 0))
        ratio = dy / BENCHMARKS["risk_free_rate"] if BENCHMARKS["risk_free_rate"] > 0 else 0
        rate_bonus = 3 if ratio >= 5 else (2 if ratio >= 4 else (1 if ratio >= 3 else 0))
        score = min(100, base + rank_bonus + rate_bonus)
        assess = ("极高股息率，收益吸引力极强" if dy >= 7 else
                  "高股息率，收益吸引力较强" if dy >= 6 else
                  "较高股息率，收益表现良好" if dy >= 5 else
                  "中等股息率" if dy >= 4 else
                  "股息率偏低" if dy >= 3 else "股息率较低")
        detail = {"score": round(score, 1), "dividend_yield": dy,
                  "vs_risk_free": f"{ratio:.1f}倍无风险利率",
                  "vs_deposit_3y": f"{dy / BENCHMARKS['deposit_rate_3y']:.1f}倍3年定存",
                  "assessment": assess}
        return score, detail

    def score_valuation_safety(self):
        pe, pb = self.stock_data["pe_dynamic"], self.stock_data["pb"]
        price = self.stock_data["price"]
        h52, l52 = self.stock_data["high_52w"], self.stock_data["low_52w"]
        # PE评分(30分)
        if pe <= 0: pe_s = 0
        elif pe <= 4: pe_s = 30
        elif pe <= 5: pe_s = 28
        elif pe <= 6: pe_s = 25
        elif pe <= 7: pe_s = 22
        elif pe <= 8: pe_s = 18
        elif pe <= 10: pe_s = 14
        else: pe_s = max(5, 14 - (pe - 10))
        # PB评分(35分)
        if pb <= 0.3: pb_s = 35
        elif pb <= 0.4: pb_s = 33
        elif pb <= 0.5: pb_s = 30
        elif pb <= 0.6: pb_s = 27
        elif pb <= 0.7: pb_s = 24
        elif pb <= 0.8: pb_s = 20
        elif pb <= 0.9: pb_s = 16
        elif pb <= 1.0: pb_s = 12
        else: pb_s = max(5, 12 - (pb - 1.0) * 5)
        # 52周位置(20分)
        pos = (price - l52) / (h52 - l52) if h52 > l52 > 0 else 0.5
        pos_s = 20 * (1 - pos)
        # 同业(15分)
        peer_s = 7.5
        score = min(100, pe_s + pb_s + pos_s + peer_s)
        pos_pct = f"{pos * 100:.0f}%"
        assess = ("极度低估，安全边际极高" if pb < 0.5 and pe < 6 else
                  "明显低估，安全边际较高" if pb < 0.7 and pe < 7 else
                  "估值偏低，有一定安全边际" if pb < 0.9 and pe < 8 else "估值适中")
        detail = {"score": round(score, 1), "pe": pe, "pb": pb,
                  "position_52w": pos_pct, "is_below_net_asset": pb < 1.0,
                  "assessment": assess}
        return score, detail

    def score_dividend_continuity(self):
        if not self.dividend_history:
            return 50, {"score": 50, "years_with_dividend": "N/A",
                        "recent_dividends": [], "avg_payout_ratio": "N/A",
                        "assessment": "缺少历史分红数据"}
        years_cnt = len(set(h["year"] for h in self.dividend_history if h["cash_per_share"] > 0))
        if years_cnt >= 15: c_s = 30
        elif years_cnt >= 10: c_s = 25 + (years_cnt - 10)
        elif years_cnt >= 5: c_s = 15 + (years_cnt - 5) * 2
        else: c_s = years_cnt * 4
        amounts = [h["cash_per_share"] for h in self.dividend_history if h["cash_per_share"] > 0]
        # 稳定性(25分)
        if len(amounts) >= 3:
            mean_a = sum(amounts) / len(amounts)
            cv = ((sum((a - mean_a)**2 for a in amounts) / len(amounts))**0.5 / mean_a) if mean_a > 0 else 1
            stab_s = 25 if cv <= 0.1 else (22 if cv <= 0.2 else (18 if cv <= 0.3 else (13 if cv <= 0.5 else 8)))
        else: stab_s = 12
        # 增长(25分)
        grow_s = 12
        if len(amounts) >= 2:
            grow_s = 20 if amounts[0] > amounts[-1] else (12 if amounts[0] == amounts[-1] else 8)
        # 分红率(20分)
        payouts = [h["payout_ratio"] for h in self.dividend_history if h.get("payout_ratio") and h["payout_ratio"] > 0]
        pay_s = 10
        avg_pay = 0
        if payouts:
            avg_pay = sum(payouts) / len(payouts)
            pay_s = 20 if 30 <= avg_pay <= 50 else (16 if 25 <= avg_pay <= 60 else 10)
        score = min(100, c_s + stab_s + grow_s + pay_s)
        assess = ("长期稳定分红，持续性极强" if years_cnt >= 15 else
                  "分红历史悠久，持续性良好" if years_cnt >= 10 else
                  "分红持续性尚可" if years_cnt >= 5 else "分红历史较短")
        detail = {"score": round(score, 1), "years_with_dividend": years_cnt,
                  "recent_dividends": amounts[:5],
                  "avg_payout_ratio": f"{avg_pay:.1f}%" if payouts else "N/A",
                  "assessment": assess}
        return score, detail

    def score_fundamentals(self):
        pe, pb = self.stock_data["pe_dynamic"], self.stock_data["pb"]
        mv, dy = self.stock_data["total_mv"], self.stock_data["dividend_yield"]
        roe = (pb / pe * 100) if pe > 0 else 0
        roe_s = 30 if roe >= 12 else (26 if roe >= 10 else (22 if roe >= 8 else (16 if roe >= 6 else max(5, roe * 2))))
        mv_s = 20 if mv >= 10000 else (18 if mv >= 5000 else (16 if mv >= 2000 else (14 if mv >= 1000 else (11 if mv >= 500 else 8))))
        est_payout = dy * pe / 100 if pe > 0 else 0
        pay_s = 25 if 0.25 <= est_payout <= 0.5 else (20 if 0.20 <= est_payout <= 0.6 else 12)
        graham = pe * pb if pe > 0 and pb > 0 else 99
        qual_s = 25 if graham < 3 else (22 if graham < 4.5 else (18 if graham < 6 else (14 if graham < 10 else 8)))
        score = min(100, roe_s + mv_s + pay_s + qual_s)
        assess = ("基本面稳健，盈利能力强" if roe >= 10 and mv >= 2000 else
                  "基本面较好" if roe >= 8 else "基本面中等" if roe >= 6 else "基本面偏弱")
        detail = {"score": round(score, 1), "implied_roe": f"{roe:.1f}%",
                  "market_cap": f"{mv:.0f}亿", "est_payout_ratio": f"{est_payout*100:.1f}%",
                  "graham_number": f"{graham:.1f}", "assessment": assess}
        return score, detail

    def score_growth_potential(self):
        price, pb = self.stock_data["price"], self.stock_data["pb"]
        h52, l52 = self.stock_data["high_52w"], self.stock_data["low_52w"]
        ytd_chg = 0
        if self.ytd_data and self.ytd_data.get("open", 0) > 0:
            ytd_chg = (price - self.ytd_data["open"]) / self.ytd_data["open"] * 100
        ytd_s = (28 if ytd_chg >= 20 else 25 if ytd_chg >= 10 else 22 if ytd_chg >= 5 else
                 18 if ytd_chg >= 0 else 14 if ytd_chg >= -5 else 10 if ytd_chg >= -10 else 5)
        repair_s = 20
        if 0 < pb < 1:
            upside = (1.0 / pb - 1) * 100
            repair_s = 40 if upside >= 100 else (35 if upside >= 60 else (30 if upside >= 40 else 25))
        elif pb >= 1: repair_s = 10
        from_high = (h52 - price) / h52 * 100 if h52 > 0 else 0
        high_s = 28 if from_high >= 30 else (24 if from_high >= 20 else (18 if from_high >= 10 else 10))
        score = min(100, ytd_s + repair_s + high_s)
        assess = (f"深度破净(PB={pb:.2f})，估值修复空间极大" if pb < 0.5 else
                  f"破净明显(PB={pb:.2f})，有较大修复潜力" if pb < 0.7 else
                  f"破净状态(PB={pb:.2f})，存在修复机会" if pb < 1 else "需依赖业绩驱动")
        detail = {"score": round(score, 1), "ytd_change": f"{ytd_chg:+.2f}%",
                  "pb_repair_space": f"{((1/pb-1)*100):.0f}%" if 0 < pb < 1 else "N/A",
                  "from_52w_high": f"{from_high:.1f}%", "assessment": assess}
        return score, detail

    def score_market_performance(self):
        turnover = self.stock_data["turnover_rate"]
        circ_mv = self.stock_data["circ_mv"]
        h52, l52 = self.stock_data["high_52w"], self.stock_data["low_52w"]
        liq_s = 35 if circ_mv >= 5000 else (30 if circ_mv >= 2000 else (25 if circ_mv >= 1000 else (20 if circ_mv >= 500 else 12)))
        vol = (h52 - l52) / l52 * 100 if l52 > 0 else 50
        vol_s = 35 if vol <= 15 else (30 if vol <= 25 else (25 if vol <= 35 else (18 if vol <= 50 else 10)))
        turn_s = 30 if 0.2 <= turnover <= 1.5 else (22 if 0.1 <= turnover <= 3 else 12)
        score = min(100, liq_s + vol_s + turn_s)
        assess = ("流动性充足，波动温和" if circ_mv >= 2000 and vol <= 30 else
                  "流动性较好" if circ_mv >= 1000 else "流动性一般" if circ_mv >= 200 else "流动性偏弱")
        detail = {"score": round(score, 1), "circ_mv": f"{circ_mv:.0f}亿",
                  "volatility_52w": f"{vol:.1f}%", "turnover_rate": f"{turnover:.2f}%",
                  "assessment": assess}
        return score, detail

    # ==================== 综合评估 ====================
    def evaluate(self, stock_code, code6=None):
        if code6 is None:
            code6 = stock_code[2:]
        print("\n" + "=" * 70)
        print("📊 股息投资综合评估系统")
        print("=" * 70)
        self.fetch_realtime_data(stock_code)
        self.fetch_dividend_history(code6)
        self.fetch_peer_data(self._get_category(self.stock_data["name"]))
        print(f"\n⏳ 正在进行多维度评分...")
        funcs = [
            ("dividend_yield", self.score_dividend_yield),
            ("valuation_safety", self.score_valuation_safety),
            ("dividend_continuity", self.score_dividend_continuity),
            ("fundamentals", self.score_fundamentals),
            ("growth_potential", self.score_growth_potential),
            ("market_performance", self.score_market_performance),
        ]
        for key, fn in funcs:
            s, d = fn()
            self.scores[key] = {"score": s, "detail": d}
        self.total_score = round(sum(self.scores[k]["score"] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS), 1)
        for th, stars, level, desc in RATING_THRESHOLDS:
            if self.total_score >= th:
                self.rating, self.rating_desc = f"{stars} {level}", desc
                break
        conclusion = self._gen_conclusion()
        print(f"✅ 评估完成！综合评分: {self.total_score}")
        return {
            "stock_name": self.stock_data["name"], "stock_code": self.stock_data["code"],
            "price": self.stock_data["price"], "total_score": self.total_score,
            "rating": self.rating, "rating_desc": self.rating_desc,
            "scores": self.scores, "conclusion": conclusion,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _gen_conclusion(self):
        name = self.stock_data["name"]
        dy = self.stock_data["dividend_yield"]
        pe, pb = self.stock_data["pe_dynamic"], self.stock_data["pb"]
        price = self.stock_data["price"]
        dim_names = {
            "dividend_yield": "股息收益", "valuation_safety": "估值安全边际",
            "dividend_continuity": "分红持续性", "fundamentals": "基本面稳健度",
            "growth_potential": "成长潜力", "market_performance": "市场表现",
        }
        sorted_d = sorted(self.scores.items(), key=lambda x: x[1]["score"], reverse=True)
        strengths = [(dim_names[k], v["score"]) for k, v in sorted_d if v["score"] >= 75]
        weaknesses = [(dim_names[k], v["score"]) for k, v in sorted_d if v["score"] < 60]
        lines = [f"【综合评估】{name}（现价{price:.2f}元）综合评分 {self.total_score} 分，评级 {self.rating}。",
                 "", f"【核心指标】股息率(TTM) {dy:.2f}%，PE {pe:.2f}倍，PB {pb:.2f}倍。",
                 f"   股息率较3年定存({BENCHMARKS['deposit_rate_3y']}%)高出 {dy - BENCHMARKS['deposit_rate_3y']:.2f}个百分点，"
                 f"是无风险利率的 {dy/BENCHMARKS['risk_free_rate']:.1f} 倍。", ""]
        if strengths:
            lines.append(f"【优势维度】" + "、".join(f"{n}({s:.0f}分)" for n, s in strengths))
        if weaknesses:
            lines.append(f"【待改善】" + "、".join(f"{n}({s:.0f}分)" for n, s in weaknesses))
        lines.append("")
        ts = self.total_score
        if ts >= 80:
            lines.append(f"【投资建议】{name}是极佳的高股息投资标的。高股息率+低估值构成\"下有底、上有弹性\"格局，适合长期配置。")
        elif ts >= 70:
            lines.append(f"【投资建议】{name}是优质的股息投资选择，适合作为高股息策略的核心持仓。")
        elif ts >= 60:
            lines.append(f"【投资建议】{name}具有一定股息投资价值，可作为分散化组合的配置标的。")
        elif ts >= 50:
            lines.append(f"【投资建议】{name}的股息投资吸引力有限，建议谨慎评估。")
        else:
            lines.append(f"【投资建议】{name}当前不太适合作为股息投资标的。")
        lines += ["", "【风险提示】以上评估基于历史数据和当前市场指标，不构成投资建议。投资有风险，决策需谨慎。"]
        return "\n".join(lines)
