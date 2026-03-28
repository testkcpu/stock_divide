#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股息投资综合评估系统 - 报告输出与主入口
======================================
用法:
  python evaluate_stock.py                    # 交互模式，手动输入代码
  python evaluate_stock.py sh601166           # 直接评估兴业银行
  python evaluate_stock.py sh601166 --image   # 评估并生成雷达图
  python evaluate_stock.py --batch            # 批量评估所有银行并排名
"""

import sys
import os
import argparse
from datetime import datetime
from dividend_evaluator import DividendEvaluator, SCORE_WEIGHTS, BENCHMARKS
from bank_dividend import BANK_STOCKS


# ==================== 文本报告输出 ====================
def print_report(report):
    """打印格式化的评估报告"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + "股息投资综合评估报告".center(58) + "║")
    print("║" + f"{report['stock_name']}({report['stock_code']})".center(60) + "║")
    print("╚" + "═" * 68 + "╝")

    print(f"\n📋 基础信息")
    print(f"   {'标的名称:':<12} {report['stock_name']}")
    print(f"   {'股票代码:':<12} {report['stock_code']}")
    print(f"   {'当前价格:':<12} {report['price']:.2f}元")
    print(f"   {'评估时间:':<12} {report['timestamp']}")

    print(f"\n{'─' * 70}")
    print(f"🏆 综合评分: {report['total_score']} / 100    评级: {report['rating']}")
    print(f"   {report['rating_desc']}")
    print(f"{'─' * 70}")

    dim_display = [
        ("dividend_yield",      "💰 股息收益"),
        ("valuation_safety",    "🛡️  估值安全边际"),
        ("dividend_continuity", "📈 分红持续性"),
        ("fundamentals",        "🏦 基本面稳健度"),
        ("growth_potential",    "🚀 成长潜力"),
        ("market_performance",  "📊 市场表现"),
    ]

    print(f"\n📊 六维评分明细:")
    print(f"{'─' * 70}")
    for key, label in dim_display:
        sd = report["scores"][key]
        s = sd["score"]
        w = SCORE_WEIGHTS[key]
        weighted = s * w
        bar_len = int(s / 100 * 25)
        bar = "█" * bar_len + "░" * (25 - bar_len)
        print(f"  {label:<16} {bar} {s:>5.1f}/100 (权重{w*100:.0f}%, 加权{weighted:>5.1f})")
        if "assessment" in sd["detail"]:
            print(f"  {'':>16} ↳ {sd['detail']['assessment']}")
        print()

    # 详细指标
    print(f"{'─' * 70}")
    print(f"📋 关键指标详情:\n")

    d1 = report["scores"]["dividend_yield"]["detail"]
    print(f"   💰 股息收益:")
    print(f"      股息率(TTM): {d1['dividend_yield']:.2f}%")
    print(f"      vs无风险利率: {d1['vs_risk_free']}")
    print(f"      vs3年定存:   {d1['vs_deposit_3y']}")

    d2 = report["scores"]["valuation_safety"]["detail"]
    print(f"\n   🛡️  估值安全边际:")
    print(f"      PE(动态): {d2['pe']:.2f}   PB: {d2['pb']:.2f}")
    print(f"      52周位置: {d2['position_52w']}")
    print(f"      破净状态: {'是' if d2['is_below_net_asset'] else '否'}")

    d3 = report["scores"]["dividend_continuity"]["detail"]
    print(f"\n   📈 分红持续性:")
    if isinstance(d3.get("years_with_dividend"), int):
        print(f"      连续分红年数: {d3['years_with_dividend']}年")
    if d3.get("recent_dividends"):
        recent_str = " → ".join(f"{d:.4f}" for d in d3["recent_dividends"])
        print(f"      近期每股分红: {recent_str}")
    if d3.get("avg_payout_ratio") != "N/A":
        print(f"      平均分红率:  {d3['avg_payout_ratio']}")

    d4 = report["scores"]["fundamentals"]["detail"]
    print(f"\n   🏦 基本面稳健度:")
    print(f"      隐含ROE:    {d4['implied_roe']}")
    print(f"      总市值:     {d4['market_cap']}")
    print(f"      估算分红率: {d4['est_payout_ratio']}")
    print(f"      格雷厄姆指标(PE×PB): {d4['graham_number']}")

    d5 = report["scores"]["growth_potential"]["detail"]
    print(f"\n   🚀 成长潜力:")
    print(f"      年初至今:    {d5['ytd_change']}")
    if d5.get("pb_repair_space") != "N/A":
        print(f"      PB修复空间:  {d5['pb_repair_space']}")
    print(f"      距52周高点:  {d5['from_52w_high']}")

    d6 = report["scores"]["market_performance"]["detail"]
    print(f"\n   📊 市场表现:")
    print(f"      流通市值:    {d6['circ_mv']}")
    print(f"      52周波幅:    {d6['volatility_52w']}")
    print(f"      换手率:      {d6['turnover_rate']}")

    # 结论
    print(f"\n{'═' * 70}")
    print(f"📝 评估结论:")
    print(f"{'─' * 70}")
    for line in report["conclusion"].split("\n"):
        print(f"  {line}")
    print(f"{'═' * 70}")


# ==================== 雷达图生成 ====================
def generate_radar_chart(report, output_path):
    """生成六维雷达图"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # 查找中文字体
    from bank_dividend import _find_cjk_font
    font_prop = _find_cjk_font()
    font_prop_bold = font_prop.copy()
    font_prop_bold.set_weight("bold")

    dim_labels = ["股息收益", "估值安全", "分红持续", "基本面", "成长潜力", "市场表现"]
    dim_keys = ["dividend_yield", "valuation_safety", "dividend_continuity",
                "fundamentals", "growth_potential", "market_performance"]
    dim_scores = [report["scores"][k]["score"] for k in dim_keys]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#FFFFFF")

    angles = np.linspace(0, 2 * np.pi, len(dim_labels), endpoint=False).tolist()
    scores_plot = dim_scores + [dim_scores[0]]
    angles_plot = angles + [angles[0]]

    ax.set_ylim(0, 100)
    ax.set_thetagrids(np.degrees(angles), dim_labels, fontproperties=font_prop, fontsize=13)

    # 绘制雷达图
    ax.fill(angles_plot, scores_plot, color="#E53935", alpha=0.15)
    ax.plot(angles_plot, scores_plot, color="#E53935", linewidth=2.5, marker="o", markersize=8)

    for angle, sv in zip(angles, dim_scores):
        ax.text(angle, sv + 10, f"{sv:.0f}", ha="center", va="center",
                fontsize=12, fontproperties=font_prop_bold, color="#C62828")

    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="#AAAAAA")
    ax.grid(color="#E0E0E0", linewidth=0.5)

    # 标题
    ts = report["total_score"]
    score_color = "#C62828" if ts >= 80 else ("#E65100" if ts >= 70 else ("#F57F17" if ts >= 60 else "#666"))

    fig.text(0.5, 0.96, f"{report['stock_name']}({report['stock_code']}) 股息投资评估",
             fontproperties=font_prop_bold, fontsize=18, ha="center", color="#1a2a4a")
    fig.text(0.5, 0.93, f"综合评分: {ts:.1f}分  |  {report['rating']}  |  {report['timestamp']}",
             fontproperties=font_prop, fontsize=12, ha="center", color=score_color)

    # 底部关键指标
    d1 = report["scores"]["dividend_yield"]["detail"]
    d2 = report["scores"]["valuation_safety"]["detail"]
    info_text = (f"股息率: {d1['dividend_yield']:.2f}%  |  PE: {d2['pe']:.2f}  |  PB: {d2['pb']:.2f}  |  "
                 f"价格: {report['price']:.2f}元")
    fig.text(0.5, 0.04, info_text, fontproperties=font_prop, fontsize=11,
             ha="center", color="#666666")
    fig.text(0.5, 0.01, "⚠️ 此报告仅供参考，不构成投资建议",
             fontproperties=font_prop, fontsize=9, ha="center", color="#AAAAAA")

    plt.tight_layout(rect=[0, 0.05, 1, 0.92])
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor="#FFFFFF", edgecolor="none")
    plt.close(fig)
    print(f"\n🖼️  雷达图已保存至: {output_path}")


# ==================== 批量评估 ====================
def batch_evaluate():
    """批量评估所有银行并排名"""

    results = []
    total = len(BANK_STOCKS)

    for i, (code, name) in enumerate(BANK_STOCKS, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{total}] 评估 {name} ({code})...")
        try:
            ev = DividendEvaluator()
            report = ev.evaluate(code)
            results.append(report)
        except Exception as e:
            print(f"⚠️ {name} 评估失败: {e}")
            continue

    # 按综合评分排序
    results.sort(key=lambda x: x["total_score"], reverse=True)

    # 输出排名表
    print("\n\n" + "=" * 90)
    print("📊 股息投资综合评估排行榜".center(80))
    print("=" * 90)

    header = (f"{'排名':>4} │ {'银行':<10} │ {'代码':<8} │ {'综合评分':>8} │ {'评级':<20} │ "
              f"{'股息率':>6} │ {'PE':>6} │ {'PB':>5}")
    print(header)
    print("─" * 90)

    for i, r in enumerate(results, 1):
        dy = r["scores"]["dividend_yield"]["detail"]["dividend_yield"]
        pe = r["scores"]["valuation_safety"]["detail"]["pe"]
        pb = r["scores"]["valuation_safety"]["detail"]["pb"]
        print(f"{i:>4} │ {r['stock_name']:<10} │ {r['stock_code']:<8} │ {r['total_score']:>7.1f}分 │ "
              f"{r['rating']:<20} │ {dy:>5.2f}% │ {pe:>6.2f} │ {pb:>5.2f}")

    print("─" * 90)
    print(f"\n共评估 {len(results)} 只银行")
    if results:
        print(f"🥇 最佳: {results[0]['stock_name']} ({results[0]['total_score']:.1f}分)")
        print(f"🥈 第二: {results[1]['stock_name']} ({results[1]['total_score']:.1f}分)" if len(results) > 1 else "")
        print(f"🥉 第三: {results[2]['stock_name']} ({results[2]['total_score']:.1f}分)" if len(results) > 2 else "")

    # 保存CSV
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_ranking.csv")
    try:
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write("排名,银行,代码,综合评分,评级,股息率,PE,PB\n")
            for i, r in enumerate(results, 1):
                dy = r["scores"]["dividend_yield"]["detail"]["dividend_yield"]
                pe = r["scores"]["valuation_safety"]["detail"]["pe"]
                pb = r["scores"]["valuation_safety"]["detail"]["pb"]
                f.write(f"{i},{r['stock_name']},{r['stock_code']},{r['total_score']:.1f},"
                        f"{r['rating']},{dy:.2f},{pe:.2f},{pb:.2f}\n")
        print(f"\n💾 排名数据已保存至: {csv_path}")
    except Exception as e:
        print(f"⚠️ CSV保存失败: {e}")

    return results


# ==================== 股票代码映射 ====================
# 方便用户直接输入简短代码
CODE_MAP = {}
for _code, _name in BANK_STOCKS:
    pure = _code[2:]
    CODE_MAP[pure] = _code
    CODE_MAP[_name] = _code
    CODE_MAP[_code] = _code


def resolve_code(user_input):
    """解析用户输入的代码，支持多种格式"""
    user_input = user_input.strip()
    if user_input in CODE_MAP:
        return CODE_MAP[user_input]
    # 尝试加前缀
    if user_input.isdigit() and len(user_input) == 6:
        if user_input.startswith("6"):
            return f"sh{user_input}"
        elif user_input.startswith("0") or user_input.startswith("3"):
            return f"sz{user_input}"
        elif user_input.startswith("00"):
            return f"sz{user_input}"
    return user_input


# ==================== 主入口 ====================
def main():
    parser = argparse.ArgumentParser(description="股息投资综合评估系统")
    parser.add_argument("stock_code", nargs="?", default=None,
                        help="股票代码，如 sh601166 或 601166 或 兴业银行")
    parser.add_argument("--image", action="store_true", help="生成雷达图")
    parser.add_argument("--batch", action="store_true", help="批量评估所有银行")
    parser.add_argument("--output", "-o", default=None, help="图片输出路径")
    args = parser.parse_args()

    if args.batch:
        batch_evaluate()
        return

    # 交互模式或命令行模式
    if args.stock_code is None:
        print("\n📊 股息投资综合评估系统")
        print("─" * 40)
        print("支持输入格式:")
        print("  • 腾讯代码: sh601166")
        print("  • 6位代码:  601166")
        print("  • 银行名称: 兴业银行")
        print("  • 输入 'batch' 批量评估所有银行")
        print("  • 输入 'quit' 退出")
        print("─" * 40)

        while True:
            user_input = input("\n请输入股票代码或名称: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 再见！")
                break
            if user_input.lower() == "batch":
                batch_evaluate()
                continue

            stock_code = resolve_code(user_input)
            try:
                ev = DividendEvaluator()
                report = ev.evaluate(stock_code)
                print_report(report)

                # 询问是否生成图片
                gen_img = input("\n是否生成雷达图? (y/n): ").strip().lower()
                if gen_img in ("y", "yes", "是"):
                    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            f"eval_{report['stock_code']}.png")
                    generate_radar_chart(report, img_path)
            except Exception as e:
                print(f"❌ 评估失败: {e}")
                import traceback
                traceback.print_exc()
    else:
        stock_code = resolve_code(args.stock_code)
        ev = DividendEvaluator()
        report = ev.evaluate(stock_code)
        print_report(report)

        if args.image:
            img_path = args.output or os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"eval_{report['stock_code']}.png")
            generate_radar_chart(report, img_path)


if __name__ == "__main__":
    main()
