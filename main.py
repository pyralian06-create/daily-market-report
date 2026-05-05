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
from datetime import datetime
from pathlib import Path

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


def save_report(report: str, label: str, date_str: str) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    slug = "morning" if "晨" in label else "evening"
    path = REPORTS_DIR / f"{date_str}_{slug}.txt"
    path.write_text(report, encoding="utf-8")
    logger.info("报告已保存: %s", path)


def collect_morning() -> dict:
    """晨报（9:00）：全球经济指标 + 全球指数行情 + 财经资讯"""
    logger.info("=== 开始采集晨报数据 ===")
    data = {"report_date": datetime.now().strftime("%Y-%m-%d")}

    logger.info("[1/3] 采集全球经济指标（国债/利率）...")
    try:
        eco = GlobalEconomyCollector().collect_all()
        intl = IntlMacroCollector().collect_all()
        data["global_economy"] = {**eco, **intl}
        logger.info("  全球经济指标采集完成")
    except Exception as e:
        logger.error("  全球经济指标采集失败: %s", e)
        data["global_economy"] = {"error": str(e)}

    logger.info("[2/3] 采集全球指数行情（A股/美股/港股/大宗商品）...")
    try:
        data["global_macro"] = GlobalMacroCollector().collect_all()
        logger.info("  全球指数采集完成")
    except Exception as e:
        logger.error("  全球指数采集失败: %s", e)
        data["global_macro"] = {"error": str(e)}

    logger.info("[3/3] 采集财经资讯（RSS）...")
    try:
        data["news"] = MarketNewsCollector().collect_all(top_n=5)
        logger.info("  财经资讯采集完成")
    except Exception as e:
        logger.error("  财经资讯采集失败: %s", e)
        data["news"] = {"error": str(e)}

    logger.info("=== 晨报采集完成 ===")
    return data


def collect_evening() -> dict:
    """晚报（18:00）：A股行情 + 中国宏观 + 财经资讯"""
    logger.info("=== 开始采集晚报数据 ===")
    data = {"report_date": datetime.now().strftime("%Y-%m-%d")}

    logger.info("[1/3] 采集 A 股行情...")
    try:
        data["a_stock"] = DailyMarketCollector().collect_all()
        logger.info("  A 股采集完成")
    except Exception as e:
        logger.error("  A 股采集失败: %s", e)
        data["a_stock"] = {"error": str(e)}

    logger.info("[2/3] 采集中国宏观数据...")
    try:
        data["china_macro"] = ChinaMacroCollector().collect_all()
        logger.info("  中国宏观采集完成")
    except Exception as e:
        logger.error("  中国宏观采集失败: %s", e)
        data["china_macro"] = {"error": str(e)}

    logger.info("[3/3] 采集财经资讯（RSS）...")
    try:
        data["news"] = MarketNewsCollector().collect_all(top_n=5)
        logger.info("  财经资讯采集完成")
    except Exception as e:
        logger.error("  财经资讯采集失败: %s", e)
        data["news"] = {"error": str(e)}

    logger.info("=== 晚报采集完成 ===")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="金融日报生成器")
    parser.add_argument("--morning", action="store_true", help="生成晨报（09:00）")
    parser.add_argument("--evening", action="store_true", help="生成晚报（18:00）")
    parser.add_argument("--send", action="store_true", help="采集后发送到 Telegram")
    args = parser.parse_args()

    if not args.morning and not args.evening:
        parser.print_help()
        sys.exit(0)

    reports: list[tuple[str, str]] = []

    if args.morning:
        data = collect_morning()
        logger.info("正在生成晨报 AI 摘要...")
        ai_summary = generate_morning_summary(
            data.get("global_macro", {}),
            data.get("global_economy", {}),
            data.get("news", {}),
        )
        report = format_morning_report(
            data.get("global_macro", {}),
            data.get("global_economy", {}),
            data.get("news", {}),
            data.get("report_date"),
            ai_summary=ai_summary,
        )
        save_report(report, "晨报", data.get("report_date", datetime.now().strftime("%Y-%m-%d")))
        reports.append(("晨报", report))
        if not args.send:
            print(report)

    if args.evening:
        data = collect_evening()
        logger.info("正在生成晚报 AI 摘要...")
        ai_summary = generate_evening_summary(
            data.get("a_stock", {}),
            data.get("china_macro", {}),
            data.get("news", {}),
        )
        report = format_evening_report(
            data.get("a_stock", {}),
            data.get("china_macro", {}),
            data.get("news", {}),
            data.get("report_date"),
            ai_summary=ai_summary,
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
