"""日报主程序入口

用法：
  python main.py --morning          # 采集晨报数据并打印
  python main.py --evening          # 采集晚报数据并打印
  python main.py --morning --send   # 采集晨报并发送 Telegram
  python main.py --evening --send   # 采集晚报并发送 Telegram
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import settings
from senders.telegram_sender import send_report
from collectors.a_stock_overview import DailyMarketCollector
from collectors.chinese_marco_data import ChinaMacroCollector
from collectors.global_marco_data import GlobalMacroCollector
from collectors.global_economy_data import GlobalEconomyCollector, IntlMacroCollector
from collectors.rss_news_collector import MarketNewsCollector
from reporters.morning_formatter import format_morning_report
from reporters.evening_formatter import format_evening_report
from reporters.ai_summarizer import generate_morning_summary, generate_evening_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent / "reports"

_SH = ZoneInfo("Asia/Shanghai")


def is_a_stock_open_today() -> bool:
    """今日（上海时区）A股是否开盘，查询失败时默认 True。"""
    from tushare_client import get_pro
    try:
        today = datetime.now(_SH).strftime("%Y%m%d")
        df = get_pro().trade_cal(exchange="SSE", start_date=today, end_date=today)
        if df is None or df.empty:
            return True
        return str(df.iloc[0]["is_open"]) == "1"
    except Exception as e:
        logger.warning("A股交易日历查询失败，默认视为开盘: %s", e)
        return True


def is_us_market_open_yesterday() -> bool:
    """昨日（上海时区的昨天）美股是否开盘，使用 us_tradecal 接口查询。"""
    from tushare_client import get_pro
    try:
        yesterday = (datetime.now(_SH) - timedelta(days=1)).strftime("%Y%m%d")
        df = get_pro().us_tradecal(start_date=yesterday, end_date=yesterday)
        if df is None or df.empty:
            return True
        return str(df.iloc[0]["is_open"]) == "1"
    except Exception as e:
        logger.warning("美股开盘状态查询失败，默认视为开盘: %s", e)
        return True


def save_report(report: str, label: str, date_str: str) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    slug = "morning" if "晨" in label else "evening"
    path = REPORTS_DIR / f"{date_str}_{slug}.txt"
    path.write_text(report, encoding="utf-8")
    logger.info("报告已保存: %s", path)


def collect_morning() -> dict:
    """晨报（9:00）：全球经济指标 + 全球指数行情 + 美股广度 + 财经资讯"""
    logger.info("=== 开始采集晨报数据 ===")
    data = {"report_date": datetime.now().strftime("%Y-%m-%d")}

    logger.info("[1/4] 采集全球经济指标（国债/利率）...")
    try:
        eco = GlobalEconomyCollector().collect_all()
        intl = IntlMacroCollector().collect_all()
        data["global_economy"] = {**eco, **intl}
        logger.info("  全球经济指标采集完成")
    except Exception as e:
        logger.error("  全球经济指标采集失败: %s", e)
        data["global_economy"] = {"error": str(e)}

    logger.info("[2/4] 采集全球指数行情（A股/美股/港股/大宗商品）...")
    try:
        data["global_macro"] = GlobalMacroCollector().collect_all()
        logger.info("  全球指数采集完成")
    except Exception as e:
        logger.error("  全球指数采集失败: %s", e)
        data["global_macro"] = {"error": str(e)}

    logger.info("[3/4] 采集美股行情（昨日收盘广度）...")
    try:
        from collectors.us_stock_overview import USStockCollector
        data["us_stock"] = USStockCollector().collect_all()
        logger.info("  美股采集完成")
    except Exception as e:
        logger.error("  美股采集失败: %s", e)
        data["us_stock"] = {"error": str(e)}

    logger.info("[4/4] 采集财经资讯（RSS）...")
    try:
        data["news"] = MarketNewsCollector().collect_all(top_n=10)
        logger.info("  财经资讯采集完成")
    except Exception as e:
        logger.error("  财经资讯采集失败: %s", e)
        data["news"] = {"error": str(e)}

    logger.info("=== 晨报采集完成 ===")
    return data


def collect_evening() -> dict:
    """晚报（19:00）：A股行情 + 港股行情 + 中国宏观 + 财经资讯"""
    logger.info("=== 开始采集晚报数据 ===")
    data = {"report_date": datetime.now().strftime("%Y-%m-%d")}

    logger.info("[1/5] 采集 A 股行情...")
    try:
        data["a_stock"] = DailyMarketCollector().collect_all()
        logger.info("  A 股采集完成")
    except Exception as e:
        logger.error("  A 股采集失败: %s", e)
        data["a_stock"] = {"error": str(e)}

    logger.info("[2/5] 采集港股行情...")
    try:
        from collectors.hk_stock_overview import HKStockCollector
        data["hk_stock"] = HKStockCollector().collect_all()
        logger.info("  港股采集完成")
    except Exception as e:
        logger.error("  港股采集失败: %s", e)
        data["hk_stock"] = {"error": str(e)}

    logger.info("[3/4] 采集中国宏观数据...")
    try:
        data["china_macro"] = ChinaMacroCollector().collect_all()
        logger.info("  中国宏观采集完成")
    except Exception as e:
        logger.error("  中国宏观采集失败: %s", e)
        data["china_macro"] = {"error": str(e)}

    logger.info("[4/4] 采集财经资讯（RSS）...")
    try:
        data["news"] = MarketNewsCollector().collect_all(top_n=10)
        logger.info("  财经资讯采集完成")
    except Exception as e:
        logger.error("  财经资讯采集失败: %s", e)
        data["news"] = {"error": str(e)}

    logger.info("=== 晚报采集完成 ===")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="金融日报生成器")
    parser.add_argument("--morning", action="store_true", help="生成晨报（09:00）")
    parser.add_argument("--evening", action="store_true", help="生成晚报（19:00）")
    parser.add_argument("--send", action="store_true", help="采集后发送到 Telegram")
    args = parser.parse_args()

    if not args.morning and not args.evening:
        parser.print_help()
        sys.exit(0)

    reports: list[tuple[str, str]] = []

    if args.morning:
        if not is_us_market_open_yesterday():
            logger.info("昨日美股未开盘，跳过今日晨报")
        else:
            data = collect_morning()
            logger.info("正在生成晨报 AI 摘要...")
            ai_summary = generate_morning_summary(
                data.get("global_macro", {}),
                data.get("global_economy", {}),
                data.get("news", {}),
                us_stock=data.get("us_stock", {}),
            )
            report = format_morning_report(
                data.get("global_macro", {}),
                data.get("global_economy", {}),
                data.get("news", {}),
                data.get("report_date"),
                ai_summary=ai_summary,
                us_stock=data.get("us_stock", {}),
            )
            save_report(report, "晨报", data.get("report_date", datetime.now().strftime("%Y-%m-%d")))
            reports.append(("晨报", report))
            if not args.send:
                print(report)

    if args.evening:
        if not is_a_stock_open_today():
            logger.info("今日A股未开盘，跳过晚报")
        else:
            data = collect_evening()
            logger.info("正在生成晚报 AI 摘要...")
            ai_summary = generate_evening_summary(
                data.get("a_stock", {}),
                data.get("china_macro", {}),
                data.get("news", {}),
                hk_stock=data.get("hk_stock", {}),
            )
            report = format_evening_report(
                data.get("a_stock", {}),
                data.get("china_macro", {}),
                data.get("news", {}),
                data.get("report_date"),
                ai_summary=ai_summary,
                hk_stock=data.get("hk_stock", {}),
            )
            save_report(report, "晚报", data.get("report_date", datetime.now().strftime("%Y-%m-%d")))
            reports.append(("晚报", report))
            if not args.send:
                print(report)

    if args.send:
        bot_token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not bot_token or not chat_id:
            logger.error("请先在 .env 中配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
            sys.exit(1)
        for label, report in reports:
            logger.info("正在发送 %s 到 Telegram...", label)
            ok = send_report(report, bot_token=bot_token, chat_id=chat_id)
            if ok:
                logger.info("%s 发送成功", label)
            else:
                logger.error("%s 发送失败", label)


if __name__ == "__main__":
    main()
