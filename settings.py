"""统一配置入口：从项目根目录的 .env 文件加载所有环境变量。

优先级：已有环境变量 > .env 文件。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_URL: str = os.getenv("TUSHARE_URL", "")

PROXY_URL: str = os.getenv("PROXY_URL", "http://127.0.0.1:7897")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
