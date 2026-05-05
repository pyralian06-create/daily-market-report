import os
import json
import re
from pathlib import Path
from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class CollectInput(BaseModel):
    type: str = Field(description="数据源类型，如 'a_stock_overview'")


@tool(args_schema=CollectInput)
def collect_information(type: str) -> str:
    """
    需要采集日报数据源是使用这个工具，支持的数据源类型有：
    type有几种类型
    a_stock_overview 表示 A股今日的涨跌幅信息和宏观数据
    chinese_marco 表示 中国的宏观信息
    global_marco 表示 全球市场的某些重要指数的涨跌幅以及一些宏观信息
    rss_news 表示 采集的新闻信息
    """



