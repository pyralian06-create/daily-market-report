"""AI 市场解读摘要生成器

使用 Google Gemini 对采集到的市场数据生成中文分析摘要。
任何异常（网络、超时、API KEY 缺失）均静默降级，返回 None。
"""

import concurrent.futures
import logging
from typing import Optional

import settings

logger = logging.getLogger(__name__)

_MORNING_PROMPT = """你是一位资深全球宏观策略分析师。以下是今日开盘前的全球市场快照：

【关键信号】
{signals_block}

【今日财经头条】
{headlines_block}

请用简洁的中文（400-600字）分析：
1. 昨夜美股及全球主要市场表现如何？全球风险偏好当前处于何种状态（Risk-on/Risk-off）？
2. 大宗商品、汇率、债券利率释放了哪些宏观信号？
3. 基于上述全球信号，预测今日各主要市场（A股、港股、欧亚股市）的开盘方向，明确给出看涨/看跌/震荡的判断及核心逻辑
4. 今日全球市场需重点关注的风险点或潜在催化剂有哪些？
要求：直接给出结论，无需引言，不要使用markdown标题，预测方向必须明确，语言简练。"""

# 有晨报预测时使用（含校验逻辑）
_EVENING_PROMPT = """你是一位专注于A股和港股市场的资深分析师。

【今日早报预测】
{morning_prediction}

【今日实际市场数据】
{signals_block}

【今日财经头条】
{headlines_block}

请用简洁的中文（500-700字）分析：
1. 今日A股和港股的核心驱动逻辑是什么？（资金面、情绪面、板块轮动）
2. 早报预测是否准确？若实际走势与预测有出入，请分析偏差原因（如突发事件、政策超预期、情绪急转等）
3. 北向资金和两融数据今日释放了什么信号？
4. 结合今日表现，市场短期的主要风险与机会在哪里？
要求：直接给出结论，无需引言，不要使用markdown标题，语言简练。"""

# 无晨报预测时的降级版本
_EVENING_PROMPT_NO_MORNING = """你是一位专注于A股和港股市场的资深分析师。以下是今日市场数据：

【市场数据】
{signals_block}

【今日财经头条】
{headlines_block}

请用简洁的中文（400-600字）分析：
1. 今日A股和港股的核心驱动逻辑是什么？（资金面、情绪面、板块轮动）
2. 北向资金和两融数据释放了什么信号？
3. 港股与美股（昨日收盘）数据对A股短期走势的联动影响是什么？
4. 结合宏观背景，市场短期内的主要风险与机会在哪里？
要求：直接给出结论，无需引言，不要使用markdown标题，语言简练。"""


def _load_morning_ai_summary() -> Optional[str]:
    """从当日晨报文件中提取 AI 摘要部分，供晚报校验使用。"""
    from datetime import datetime
    from pathlib import Path
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = Path(__file__).parent.parent / "reports" / f"{date_str}_morning.txt"
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        marker = "【AI 市场解读】"
        idx = content.find(marker)
        if idx == -1:
            return None
        return content[idx + len(marker):].strip()
    except Exception:
        return None


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


def _extract_morning_signals(
    global_macro: dict,
    global_economy: dict,
    us_stock: Optional[dict] = None,
) -> str:
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

    # 美股昨日广度（来自 us_daily）
    if us_stock and isinstance(us_stock, dict) and "error" not in us_stock:
        us_idx = us_stock.get("index_quotes", [])
        if isinstance(us_idx, list):
            for item in us_idx:
                if "error" not in item:
                    lines.append(f"美股{item.get('名称', '')}: {_pct_str(item)}")
        us_breadth = us_stock.get("market_breadth", {})
        if isinstance(us_breadth, dict) and "error" not in us_breadth:
            adv = us_breadth.get("上涨家数", "N/A")
            dec = us_breadth.get("下跌家数", "N/A")
            avg = us_breadth.get("市场平均涨幅", "N/A")
            lines.append(f"美股涨跌家数: {adv} 涨 / {dec} 跌  均涨幅: {avg}")

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


def _extract_evening_signals(
    a_stock: dict,
    china_macro: dict,
    hk_stock: Optional[dict] = None,
) -> str:
    lines = []

    # A股主要指数
    index_quotes = a_stock.get("index_quotes")
    if isinstance(index_quotes, list):
        for item in index_quotes:
            if "error" not in item and item.get("名称") in ("上证指数", "沪深300", "创业板指"):
                lines.append(f"{item['名称']}: {_pct_str(item)}")

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

    # 港股信号
    if hk_stock and isinstance(hk_stock, dict) and "error" not in hk_stock:
        hk_idx = hk_stock.get("index_quotes", [])
        if isinstance(hk_idx, list):
            for item in hk_idx:
                if "error" not in item and item.get("名称") == "恒生指数":
                    lines.append(f"恒生指数: {_pct_str(item)}")
                    break

    return "\n".join(lines) if lines else "暂无关键数据"


def _extract_news_headlines(news: dict) -> str:
    """提取新闻供 LLM 使用：总结性新闻附完整正文（单条≤10000字符），普通新闻附标题+摘要。"""
    parts = []
    for source, entries in news.items():
        if not isinstance(entries, list):
            continue
        for item in entries[:10]:
            title = item.get("title", "").strip()
            if not title:
                continue
            # 总结性新闻用完整正文（collector 已限制 10000 字符），否则用截断摘要
            body = item.get("full_content", "").strip() or item.get("desc", "").strip()
            line = f"- [{source}] {title}\n  {body}" if body else f"- [{source}] {title}"
            parts.append(line)
    return "\n".join(parts) if parts else "暂无头条"


def generate_morning_summary(
    global_macro: dict,
    global_economy: dict,
    news: dict,
    timeout: int = 120,
    us_stock: Optional[dict] = None,
) -> Optional[str]:
    if not settings.GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY 未配置，跳过 AI 摘要")
        return None
    try:
        signals = _extract_morning_signals(global_macro, global_economy, us_stock=us_stock)
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
    hk_stock: Optional[dict] = None,
) -> Optional[str]:
    if not settings.GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY 未配置，跳过 AI 摘要")
        return None
    try:
        signals = _extract_evening_signals(a_stock, china_macro, hk_stock=hk_stock)
        headlines = _extract_news_headlines(news)
        morning_summary = _load_morning_ai_summary()
        if morning_summary:
            prompt = _EVENING_PROMPT.format(
                morning_prediction=morning_summary,
                signals_block=signals,
                headlines_block=headlines,
            )
        else:
            logger.info("未找到今日晨报 AI 摘要，使用无对照版晚报 prompt")
            prompt = _EVENING_PROMPT_NO_MORNING.format(signals_block=signals, headlines_block=headlines)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call_llm, prompt)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning("AI 晚报摘要生成超时（>%ds），已跳过", timeout)
    except Exception as e:
        logger.warning("AI 晚报摘要生成失败: %s", e)
    return None
