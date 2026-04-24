"""日报主程序

用法：
  python main.py --dry-run    # 采集并打印到终端，不发送
  python main.py --send       # 采集并发送（WeCom，阶段二实现）
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

from collectors import a_share, us_stock, macro, news

CONFIG_PATH = Path(__file__).parent / "config" / "config.yaml"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.warning("config.yaml 不存在，使用空配置")
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_all(config: dict) -> dict:
    logger.info("=== 开始采集 ===")
    return {
        "a_share": a_share.collect(),
        "us_stock": us_stock.collect(config),
        "macro":    macro.collect(config),
        "news":     news.collect(config),
    }


def print_report(data: dict) -> None:
    print("\n" + "=" * 60)
    print("【市场日报】干运行预览")
    print("=" * 60)

    # A股
    print("\n【A股行情】")
    for idx in data["a_share"].get("indices", []):
        sign = "+" if idx["change_pct"] >= 0 else ""
        print(f"  {idx['name']}: {idx['price']} ({sign}{idx['change_pct']:.2f}%)")
    stats = data["a_share"].get("limit_stats", {})
    print(f"  涨停: {stats.get('limit_up', 0)} 家  跌停: {stats.get('limit_down', 0)} 家")

    # 热门板块
    sectors = data["a_share"].get("hot_sectors", [])
    if sectors:
        print("\n  板块热点 Top5:")
        for s in sectors[:5]:
            print(f"    {s['name']}: +{s['change_pct']:.2f}%")

    # 美股
    print("\n【美股行情】")
    for idx in data["us_stock"].get("indices", []):
        sign = "+" if idx["change_pct"] >= 0 else ""
        print(f"  {idx['name']}: {idx['price']} ({sign}{idx['change_pct']:.2f}%)")
    wl = data["us_stock"].get("watchlist", [])
    if wl:
        print("  自选股:")
        for s in wl:
            sign = "+" if s["change_pct"] >= 0 else ""
            print(f"    {s['symbol']}: {s['price']} ({sign}{s['change_pct']:.2f}%)")

    # 宏观
    print("\n【宏观数据】")
    china = data["macro"].get("china", {})
    if "usd_cny" in china:
        print(f"  美元/人民币: {china['usd_cny']['rate']}")
    if "pmi" in china:
        print(f"  中国PMI: {china['pmi']['value']} ({china['pmi']['date']})")
    if "cpi" in china:
        print(f"  中国CPI: {china['cpi']['value']}% ({china['cpi']['date']})")
    us = data["macro"].get("us", {})
    if "fed_funds_rate" in us:
        print(f"  美联储利率: {us['fed_funds_rate']['value']}%")
    if "us_10y_yield" in us:
        print(f"  美国10年期国债: {us['us_10y_yield']['value']}%")
    for c in data["macro"].get("commodities", []):
        sign = "+" if c["change_pct"] >= 0 else ""
        print(f"  {c['name']}: {c['price']} ({sign}{c['change_pct']:.2f}%)")

    # 新闻
    print("\n【财经新闻】")
    articles = data["news"].get("articles", [])
    for i, a in enumerate(articles[:10], 1):
        print(f"  {i}. [{a['source']}] {a['title']}")
    stats = data["news"].get("source_stats", {})
    print(f"\n  来源统计: {stats}")

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="金融日报生成器")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="采集并打印，不发送")
    group.add_argument("--send",    action="store_true", help="采集并发送到企业微信")
    args = parser.parse_args()

    config = load_config()
    data = collect_all(config)

    if args.dry_run:
        print_report(data)
        print("\n[dry-run] 原始数据已输出。如需查看完整 JSON，重定向到文件：")
        print("  python main.py --dry-run > output.json")
    else:
        logger.warning("--send 功能在阶段二实现（WeCom机器人接入后启用）")


if __name__ == "__main__":
    main()
