"""晨报格式化：全球指数行情 + 全球经济指标（国债/利率）+ 财经资讯"""

from datetime import datetime
from typing import Optional


def format_morning_report(
    global_macro: dict,
    global_economy: dict,
    news: dict,
    report_date: Optional[str] = None,
    ai_summary: Optional[str] = None,
) -> str:
    date = report_date or datetime.now().strftime("%Y-%m-%d")
    sections = [
        f"=== 晨报 {date} ===\n",
        _format_global_macro_section(global_macro),
        _format_global_economy_section(global_economy),
        _format_news_section(news),
    ]
    if ai_summary:
        sections.append("【AI 市场解读】\n" + ai_summary)
    return "\n".join(sections)


# ── 全球指数行情 ────────────────────────────────────────────────────────

def _format_global_macro_section(global_macro: dict) -> str:
    lines = ["【全球指数行情】"]
    if not global_macro:
        lines.append("  暂无数据")
        return "\n".join(lines)
    if "error" in global_macro:
        lines.append(f"  [失败] {global_macro['error']}")
        return "\n".join(lines)
    for market, rows in global_macro.items():
        lines.append(f"  ── {market} ──")
        if isinstance(rows, dict):
            lines.append(f"    [失败] {rows.get('error', '未知错误')}")
            continue
        for item in rows:
            if "error" in item:
                lines.append(f"    {item['名称']:<12} [失败] {item['error']}")
                continue
            pct = item.get("涨跌幅(%)")
            sign = "+" if pct and pct > 0 else ""
            pct_str = f"{sign}{pct}%" if pct is not None else "N/A"
            lines.append(
                f"    {item['名称']:<12} {item['最新价']:>12.4f}  {pct_str:>9}  {item.get('交易日期', '')}"
            )
    return "\n".join(lines)


# ── 全球经济指标（国债 / 利率）──────────────────────────────────────────

def _format_global_economy_section(global_economy: dict) -> str:
    lines = ["【全球经济指标】"]
    if not global_economy:
        lines.append("  暂无数据")
        return "\n".join(lines)
    if "error" in global_economy:
        lines.append(f"  [失败] {global_economy['error']}")
        return "\n".join(lines)

    # 美国国债（GlobalEconomyCollector.get_us_treasury_yield）
    us_tsy = global_economy.get("us_treasury", {})
    if us_tsy and "error" not in us_tsy:
        lines.append("  ── 美国国债收益率 ──")
        for k in ("日期", "2年期(%)", "10年期(%)", "30年期(%)", "10Y-2Y利差(%)"):
            v = us_tsy.get(k)
            if v is not None:
                lines.append(f"    {k:<18} {v}")
        meaning = us_tsy.get("意义", "")
        if meaning:
            lines.append(f"    → {meaning}")
    elif us_tsy.get("error"):
        lines.append(f"  美国国债: [失败] {us_tsy['error']}")

    # 利率体系（IntlMacroCollector）
    _SKIP = {"指标", "意义", "HIBOR-SHIBOR利差说明"}
    rate_sections = [
        ("us_rates",  "美国利率体系（T-bill + 国债）"),
        ("libor_usd", "LIBOR USD"),
        ("shibor",    "SHIBOR"),
        ("hibor",     "HIBOR"),
    ]
    for key, label in rate_sections:
        info = global_economy.get(key, {})
        if not info:
            continue
        if "error" in info:
            lines.append(f"  {label}: [失败] {info['error']}")
            continue
        lines.append(f"  ── {label} ──")
        meaning = info.get("意义", "")
        for k, v in info.items():
            if k in _SKIP or v is None:
                continue
            lines.append(f"    {k:<18} {v}")
        if meaning:
            lines.append(f"    → {meaning}")

    return "\n".join(lines)


# ── 财经资讯 ─────────────────────────────────────────────────────────────

def _format_news_section(news: dict) -> str:
    lines = ["【财经资讯】"]
    if not news:
        lines.append("  暂无资讯")
        return "\n".join(lines)
    if "error" in news:
        lines.append(f"  [失败] {news['error']}")
        return "\n".join(lines)
    for source, entries in news.items():
        lines.append(f"\n## {source}")
        if isinstance(entries, dict) and "error" in entries:
            lines.append(f"> [失败] {entries['error']}")
            continue
        if not entries:
            lines.append("> 暂无数据或接口限流。")
            continue
        for i, item in enumerate(entries, 1):
            title = item.get("title", "")
            link = item.get("link", "")
            date_str = item.get("date", "")
            desc = item.get("desc", "")
            title_line = f"**{i}. [{title}]({link})**" if link else f"**{i}. {title}**"
            lines.append(title_line)
            lines.append(f"* {date_str}")
            if desc and desc not in title:
                lines.append(f"> {desc}")
            lines.append("")
        lines.append("---")
    return "\n".join(lines)
