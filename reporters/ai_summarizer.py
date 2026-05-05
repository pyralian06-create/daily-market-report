"""AI 市场解读摘要生成器

使用 Google Gemini 对采集到的市场数据生成中文分析摘要。
任何异常（网络、超时、API KEY 缺失）均静默降级，返回 None。
"""

import concurrent.futures
import logging
from typing import Optional

import settings

logger = logging.getLogger(__name__)

_MORNING_PROMPT = """你是一位专注于A股和港股市场的资深分析师。以下是今日开盘前的全球市场快照：

【关键信号】
{signals_block}

【今日财经头条】
{headlines_block}

请用简洁的中文（400-600字）分析：
1. 全球市场当前处于风险偏好上行还是下行模式？主要依据是什么？
2. 上述信号对今日A股（沪深300、创业板）和港股开盘走势有何影响？
3. 有无需要特别关注的尾部风险或催化剂？
要求：直接给出结论，无需引言，不要使用markdown标题，语言简练。"""

_EVENING_PROMPT = """你是一位专注于A股市场的资深分析师。以下是今日A股收盘数据：

【市场数据】
{signals_block}

【今日财经头条】
{headlines_block}

请用简洁的中文（400-600字）分析：
1. 今日A股的核心驱动逻辑是什么？（资金面、情绪面、板块轮动）
2. 北向资金和两融数据释放了什么信号？
3. 结合宏观背景，市场短期内的主要风险与机会在哪里？
要求：直接给出结论，无需引言，不要使用markdown标题，语言简练。"""


def _call_llm(prompt: str) -> str:
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.7,
    )
    result = llm.invoke(prompt)
    content = result.content
    if isinstance(content, list):
        content = " ".join(
            c.get("text", "") if isinstance(c, dict) else str(c) for c in content
        )
    return content.strip()


def _find(rows: list, name_substr: str) -> Optional[dict]:
    for item in rows:
        if name_substr in str(item.get("名称", "")):
            return item
    return None


def _pct_str(item: Optional[dict]) -> str:
    if not item:
        return "N/A"
    pct = item.get("涨跌幅(%)")
    price = item.get("最新价")
    if pct is None:
        return f"{price}" if price is not None else "N/A"
    sign = "+" if pct > 0 else ""
    return f"{price} ({sign}{pct}%)"


def _extract_morning_signals(global_macro: dict, global_economy: dict) -> str:
    lines = []

    rates = global_macro.get("宏观利率", [])
    if isinstance(rates, list):
        for name, substr in [("美债10Y(%)", "美债10Y"), ("美元指数", "美元指数"), ("VIX恐慌指数", "VIX")]:
            item = _find(rates, substr)
            if item:
                lines.append(f"{name}: {_pct_str(item)}")

    us = global_macro.get("美股", [])
    if isinstance(us, list):
        for name, substr in [("标普500期货", "标普"), ("纳指期货", "纳斯达克")]:
            item = _find(us, substr)
            if item:
                lines.append(f"{name}: {_pct_str(item)}")

    hk = global_macro.get("港股&欧亚", [])
    if isinstance(hk, list):
        item = _find(hk, "恒生指数")
        if item:
            lines.append(f"恒生指数: {_pct_str(item)}")

    comm = global_macro.get("大宗商品", [])
    if isinstance(comm, list):
        for name, substr in [("纽约黄金", "黄金"), ("布伦特原油", "布伦特")]:
            item = _find(comm, substr)
            if item:
                lines.append(f"{name}: {_pct_str(item)}")

    us_tsy = global_economy.get("us_treasury", {})
    if isinstance(us_tsy, dict) and "error" not in us_tsy:
        spread = us_tsy.get("10Y-2Y利差(%)")
        if spread is not None:
            lines.append(f"美债10Y-2Y利差: {spread}%")

    shibor = global_economy.get("shibor", {})
    if isinstance(shibor, dict) and "error" not in shibor:
        on = shibor.get("隔夜(%)")
        if on is not None:
            lines.append(f"SHIBOR隔夜: {on}%")

    return "\n".join(lines) if lines else "暂无关键信号"


def _extract_evening_signals(a_stock: dict, china_macro: dict) -> str:
    lines = []

    breadth = a_stock.get("market_breadth", {})
    if isinstance(breadth, dict) and "error" not in breadth:
        lines.append(f"成交额: {breadth.get('总成交额(亿元)', 'N/A')} 亿元")
        lines.append(
            f"涨跌家数: {breadth.get('上涨家数', 'N/A')} 涨 / "
            f"{breadth.get('下跌家数', 'N/A')} 跌"
            f"  涨停: {breadth.get('涨停家数', 'N/A')}"
        )
        lines.append(f"市场平均涨幅: {breadth.get('市场平均涨幅', 'N/A')}")
        lines.append(f"全天重心: {breadth.get('全天重心位置', 'N/A')}")

    sector = a_stock.get("sector_fund_flow", {})
    if isinstance(sector, dict) and "error" not in sector:
        gainers = sector.get("涨幅前5", [])[:3]
        losers = sector.get("跌幅前5", [])[:3]
        if gainers:
            top = "、".join(
                f"{r.get('板块','?')}({r.get('涨跌幅(%)','?')}%)" for r in gainers
            )
            lines.append(f"涨幅领先板块: {top}")
        if losers:
            bot = "、".join(
                f"{r.get('板块','?')}({r.get('涨跌幅(%)','?')}%)" for r in losers
            )
            lines.append(f"跌幅领先板块: {bot}")

    hsgt = a_stock.get("hsgt_flow", {})
    if isinstance(hsgt, dict) and "error" not in hsgt:
        north = hsgt.get("北向资金合计(亿元)", "N/A")
        mood = hsgt.get("北向情绪", "")
        lines.append(f"北向资金: {north} 亿元 {mood}")

    margin = a_stock.get("margin_balance", {})
    if isinstance(margin, dict) and "error" not in margin:
        lines.append(f"两融总余额: {margin.get('两融总余额(亿元)', 'N/A')} 亿元")

    pmi = china_macro.get("pmi", {})
    if isinstance(pmi, dict) and "error" not in pmi:
        val = pmi.get("制造业PMI")
        state = pmi.get("状态", "")
        if val is not None:
            lines.append(f"制造业PMI: {val} ({state})")

    cpi = china_macro.get("cpi", {})
    if isinstance(cpi, dict) and "error" not in cpi:
        val = cpi.get("全国同比")
        if val is not None:
            lines.append(f"CPI全国同比: {val}")

    lpr = china_macro.get("lpr", {})
    if isinstance(lpr, dict) and "error" not in lpr:
        val = lpr.get("1年期")
        if val is not None:
            lines.append(f"LPR 1年期: {val}%")

    return "\n".join(lines) if lines else "暂无关键数据"


def _extract_news_headlines(news: dict) -> str:
    parts = []
    total = 0
    for source, entries in news.items():
        if not isinstance(entries, list):
            continue
        for item in entries[:3]:
            title = item.get("title", "").strip()
            if not title:
                continue
            line = f"- [{source}] {title}"
            total += len(line)
            parts.append(line)
            if total >= 600:
                break
        if total >= 600:
            break
    return "\n".join(parts) if parts else "暂无头条"


def generate_morning_summary(
    global_macro: dict,
    global_economy: dict,
    news: dict,
    timeout: int = 120,
) -> Optional[str]:
    if not settings.GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY 未配置，跳过 AI 摘要")
        return None
    try:
        signals = _extract_morning_signals(global_macro, global_economy)
        headlines = _extract_news_headlines(news)
        prompt = _MORNING_PROMPT.format(signals_block=signals, headlines_block=headlines)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call_llm, prompt)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning("AI 晨报摘要生成超时（>%ds），已跳过", timeout)
    except Exception as e:
        logger.warning("AI 晨报摘要生成失败: %s", e)
    return None


def generate_evening_summary(
    a_stock: dict,
    china_macro: dict,
    news: dict,
    timeout: int = 120,
) -> Optional[str]:
    if not settings.GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY 未配置，跳过 AI 摘要")
        return None
    try:
        signals = _extract_evening_signals(a_stock, china_macro)
        headlines = _extract_news_headlines(news)
        prompt = _EVENING_PROMPT.format(signals_block=signals, headlines_block=headlines)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call_llm, prompt)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning("AI 晚报摘要生成超时（>%ds），已跳过", timeout)
    except Exception as e:
        logger.warning("AI 晚报摘要生成失败: %s", e)
    return None
