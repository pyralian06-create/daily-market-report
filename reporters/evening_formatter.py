"""晚报格式化：A股行情（含沪深港通）+ 中国宏观 + 财经资讯"""

from datetime import datetime
from typing import Optional


def _fmt_pct(v) -> str:
    if v is None:
        return ""
    return f" ▲+{v:.2f}%" if v >= 0 else f" ▼{v:.2f}%"


def _fmt_delta(v) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else ""
    return f" ∆{sign}{v:.2f}亿"


def format_evening_report(
    a_stock: dict,
    china_macro: dict,
    news: dict,
    report_date: Optional[str] = None,
    ai_summary: Optional[str] = None,
    hk_stock: Optional[dict] = None,
) -> str:
    date = report_date or datetime.now().strftime("%Y-%m-%d")
    sections = [
        f"=== 晚报 {date} ===\n",
        _format_a_stock_section(a_stock),
        _format_hk_stock_section(hk_stock or {}),
        _format_china_macro_section(china_macro),
        _format_news_section(news),
    ]
    if ai_summary:
        sections.append("【AI 市场解读】\n" + ai_summary)
    return "\n".join(sections)


# ── A股行情 ──────────────────────────────────────────────────────────────

def _fmt_index_row(item: dict) -> str:
    if "error" in item:
        return f"    {item.get('名称', '?'):<8} [失败] {item['error']}"
    pct = item.get("涨跌幅(%)")
    chg = item.get("涨跌点")
    sign = "+" if pct is not None and pct >= 0 else ""
    pct_str = f"{sign}{pct:.2f}%" if pct is not None else "N/A"
    chg_str = f"  {sign}{chg:.2f}pt" if chg is not None else ""
    return f"    {item['名称']:<8}  {item['最新价']:>10.2f}  {pct_str:>9}{chg_str}"


def _format_a_stock_section(a_stock: dict) -> str:
    lines = ["【A 股行情】"]
    if not a_stock:
        lines.append("  暂无数据")
        return "\n".join(lines)
    if "error" in a_stock:
        lines.append(f"  [失败] {a_stock['error']}")
        return "\n".join(lines)

    # 主要指数
    index_quotes = a_stock.get("index_quotes")
    if isinstance(index_quotes, list) and index_quotes:
        lines.append("  主要指数:")
        for item in index_quotes:
            lines.append(_fmt_index_row(item))

    # 市场广度
    breadth = a_stock.get("market_breadth", {})
    if isinstance(breadth, dict) and "error" in breadth:
        lines.append(f"  市场行情: [失败] {breadth['error']}")
    elif isinstance(breadth, dict) and breadth:
        lines.append(f"  交易日期   : {breadth.get('交易日期', 'N/A')}")
        lines.append(f"  两市成交额 : {breadth.get('总成交额(亿元)', 'N/A')} 亿元{_fmt_pct(breadth.get('总成交额环比(%)'))}")
        lines.append(
            f"  涨跌家数   : {breadth.get('上涨家数', 'N/A')} 涨 / "
            f"{breadth.get('下跌家数', 'N/A')} 跌 / {breadth.get('平盘家数', 'N/A')} 平"
            f"  (涨停 {breadth.get('涨停家数', 'N/A')} / 跌停 {breadth.get('跌停家数', 'N/A')})"
        )
        lines.append(
            f"  均涨/中位  : {breadth.get('市场平均涨幅', 'N/A')} / {breadth.get('涨幅中位数', 'N/A')}"
            f"  强势: {breadth.get('强势股占比', 'N/A')}  大跌: {breadth.get('大跌股占比', 'N/A')}"
        )
        lines.append(
            f"  重心/抱团度: {breadth.get('全天重心位置', 'N/A')} / {breadth.get('资金抱团度', 'N/A')}"
        )

    # 两融余额
    margin = a_stock.get("margin_balance", {})
    if isinstance(margin, dict) and "error" in margin:
        lines.append(f"  两融余额: [失败] {margin['error']}")
    elif isinstance(margin, dict) and margin:
        lines.append(
            f"  两融余额   : {margin.get('两融总余额(亿元)', 'N/A')} 亿元{_fmt_pct(margin.get('两融总余额环比(%)'))} "
            f" 沪({margin.get('沪市日期', 'N/A')}): {margin.get('沪市两融余额(亿元)', 'N/A')}"
            f"  深({margin.get('深市日期', 'N/A')}): {margin.get('深市两融余额(亿元)', 'N/A')}"
        )

    # 行业板块
    sector = a_stock.get("sector_fund_flow", {})
    if isinstance(sector, dict) and "error" in sector:
        lines.append(f"  行业板块: [失败] {sector['error']}")
    elif isinstance(sector, dict) and sector:
        def _sector_rows(rows, label):
            lines.append(f"  {label}:")
            for i, item in enumerate(rows, 1):
                lines.append(
                    f"    {i}. {str(item.get('板块', 'N/A')):<10}"
                    f"  {item.get('涨跌幅(%)', 'N/A'):>6}%"
                    f"  净流入: {item.get('净流入(百万元)', 'N/A'):>8} 百万"
                    f"  成分股: {item.get('成分股数', 'N/A')}"
                    f"  领涨: {item.get('领涨股', 'N/A')} {item.get('领涨股涨幅(%)', '')}%"
                )
        gainers = sector.get("涨幅前5", [])
        losers  = sector.get("跌幅前5", [])
        if gainers:
            _sector_rows(gainers, f"行业涨幅 Top{len(gainers)}")
        if losers:
            _sector_rows(losers, f"行业跌幅 Top{len(losers)}")

    # 沪深港通
    hsgt = a_stock.get("hsgt_flow", {})
    if isinstance(hsgt, dict) and "error" in hsgt:
        lines.append(f"  沪深港通: [失败] {hsgt['error']}")
    elif isinstance(hsgt, dict) and hsgt:
        north = hsgt.get("北向资金合计(亿元)", "N/A")
        south = hsgt.get("南向资金合计(亿元)", "N/A")
        mood  = hsgt.get("北向情绪", "")
        lines.append(
            f"  北向资金   : {north} 亿元{_fmt_delta(hsgt.get('北向资金环比变化(亿元)'))} ({mood})"
            f"  沪股通: {hsgt.get('沪股通(亿元)', 'N/A')}  深股通: {hsgt.get('深股通(亿元)', 'N/A')}"
        )
        lines.append(f"  南向资金   : {south} 亿元{_fmt_delta(hsgt.get('南向资金环比变化(亿元)'))}")

    return "\n".join(lines)


# ── 港股行情 ─────────────────────────────────────────────────────────────

def _fmt_count_delta(v) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else ""
    return f"({sign}{v})"


def _format_hk_stock_section(hk_stock: dict) -> str:
    lines = ["【港 股 行 情】"]
    if not hk_stock:
        lines.append("  暂无数据")
        return "\n".join(lines)
    if "error" in hk_stock:
        lines.append(f"  [失败] {hk_stock['error']}")
        return "\n".join(lines)

    trade_date = hk_stock.get("trade_date", "")
    if trade_date:
        lines.append(f"  交易日期   : {trade_date}")

    # 主要指数
    index_quotes = hk_stock.get("index_quotes")
    if isinstance(index_quotes, list) and index_quotes:
        lines.append("  主要指数:")
        for item in index_quotes:
            if "error" in item:
                lines.append(f"    {item.get('名称', '?'):<8} [失败] {item['error']}")
                continue
            pct = item.get("涨跌幅(%)")
            chg = item.get("涨跌点")
            sign = "+" if pct is not None and pct >= 0 else ""
            pct_str = f"{sign}{pct:.2f}%" if pct is not None else "N/A"
            chg_str = f"  {sign}{chg:.2f}pt" if chg is not None else ""
            lines.append(f"    {item['名称']:<8}  {item['最新价']:>10.2f}  {pct_str:>9}{chg_str}")

    # 市场广度
    breadth = hk_stock.get("market_breadth", {})
    if isinstance(breadth, dict) and "error" in breadth:
        lines.append(f"  市场广度: [失败] {breadth['error']}")
    elif isinstance(breadth, dict) and breadth:
        adv_delta = _fmt_count_delta(breadth.get("上涨家数环比"))
        dec_delta = _fmt_count_delta(breadth.get("下跌家数环比"))
        lines.append(
            f"  涨跌家数   : {breadth.get('上涨家数', 'N/A')}{adv_delta} 涨 / "
            f"{breadth.get('下跌家数', 'N/A')}{dec_delta} 跌 / {breadth.get('平盘家数', 'N/A')} 平"
        )
        lines.append(
            f"  总成交额   : {breadth.get('总成交额(亿港元)', 'N/A')} 亿港元"
            f"{_fmt_pct(breadth.get('成交额环比(%)'))}"
            f"  均涨幅: {breadth.get('市场平均涨幅', 'N/A')}"
        )
        lines.append(
            f"  强势/弱势  : 涨>3% {breadth.get('强势股占比(>3%)', 'N/A')}"
            f"  跌>3% {breadth.get('弱势股占比(<-3%)', 'N/A')}"
        )

    return "\n".join(lines)


# ── 中国宏观数据 ─────────────────────────────────────────────────────────

def _format_china_macro_section(china_macro: dict) -> str:
    lines = ["【中国宏观数据】"]
    if not china_macro:
        lines.append("  暂无数据")
        return "\n".join(lines)
    if "error" in china_macro:
        lines.append(f"  [失败] {china_macro['error']}")
        return "\n".join(lines)
    for key, info in china_macro.items():
        if not isinstance(info, dict):
            continue
        name = info.get("指标名称", key)
        meaning = info.get("意义", "")
        lines.append(f"  [{name}]")
        for k, v in info.items():
            if k not in ("指标名称", "意义"):
                lines.append(f"    {k}: {v}")
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
            link  = item.get("link", "")
            date_str = item.get("date", "")
            desc  = item.get("desc", "")
            title_line = f"**{i}. [{title}]({link})**" if link else f"**{i}. {title}**"
            lines.append(title_line)
            lines.append(f"* {date_str}")
            if desc and desc not in title:
                lines.append(f"> {desc}")
            lines.append("")
        lines.append("---")
    return "\n".join(lines)
