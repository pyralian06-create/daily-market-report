"""定时调度守护进程

09:00 Asia/Shanghai → 晨报（全球宏观 + 利率 + 资讯）
17:00 Asia/Shanghai → 晚报（A 股行情 + 中国宏观 + 资讯）

启动方式：
  python scheduler.py
  nohup python scheduler.py > logs/scheduler.log 2>&1 &
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import schedule

sys.path.insert(0, str(Path(__file__).parent))

import settings
from main import collect_morning, collect_evening, save_report
from reporters.morning_formatter import format_morning_report
from reporters.evening_formatter import format_evening_report
from reporters.ai_summarizer import generate_morning_summary, generate_evening_summary
from senders.telegram_sender import send_report

LOG_PATH = Path(__file__).parent / "logs" / "scheduler.log"
logger = logging.getLogger(__name__)


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
        ],
    )


def shanghai_to_local(hour: int, minute: int) -> str:
    """将 Asia/Shanghai HH:MM 转为宿主机本地时间字符串（供 schedule 使用）。"""
    tz_sh = ZoneInfo("Asia/Shanghai")
    dt_sh = datetime.now(tz_sh).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return dt_sh.astimezone().strftime("%H:%M")


def run_morning() -> None:
    logger.info("触发晨报任务...")
    try:
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
        save_report(report, "晨报", data.get("report_date", ""))
        bot_token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not bot_token or not chat_id:
            logger.warning("Telegram 未配置（TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID），降级打印到 stdout")
            print(report)
        else:
            ok = send_report(report, bot_token=bot_token, chat_id=chat_id)
            logger.info("晨报发送%s", "成功" if ok else "失败（部分消息未到达）")
    except Exception as e:
        logger.error("晨报任务异常: %s", e)


def run_evening() -> None:
    logger.info("触发晚报任务...")
    try:
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
        save_report(report, "晚报", data.get("report_date", ""))
        bot_token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        if not bot_token or not chat_id:
            logger.warning("Telegram 未配置（TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID），降级打印到 stdout")
            print(report)
        else:
            ok = send_report(report, bot_token=bot_token, chat_id=chat_id)
            logger.info("晚报发送%s", "成功" if ok else "失败（部分消息未到达）")
    except Exception as e:
        logger.error("晚报任务异常: %s", e)


def reschedule_daily() -> None:
    schedule.clear()
    morning_local = shanghai_to_local(9, 0)
    evening_local = shanghai_to_local(17, 0)
    schedule.every().day.at(morning_local).do(run_morning)
    schedule.every().day.at(evening_local).do(run_evening)
    # 每天 00:01 重新计算，应对夏令时或时区变更
    schedule.every().day.at("00:01").do(reschedule_daily)
    logger.info("任务已注册 — 晨报: %s (本地), 晚报: %s (本地)", morning_local, evening_local)


def main() -> None:
    setup_logging()
    reschedule_daily()
    logger.info("调度守护进程已启动，按 Ctrl+C 退出")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
