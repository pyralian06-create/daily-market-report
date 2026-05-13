"""港股行情采集

数据源：Tushare Pro
  index_global — 全球指数行情（含 HSI / HKTECH / HSHKCI）

collect_all() 返回结构：
    {
        "trade_date":   "20260508",
        "index_quotes": [{"名称", "最新价", "涨跌幅(%)", "涨跌点"}, ...],
    }
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro

HK_INDEX_CODES: list[tuple[str, str]] = [
    ("恒生指数",  "HSI"),
    ("恒生科技",  "HKTECH"),
    ("恒生综合",  "HSHKCI"),
]


class HKStockCollector:
    def __init__(self):
        self.pro = get_pro()
        self.report_date = datetime.now().strftime("%Y-%m-%d")
        self.trade_date = self._find_trade_date()

    def _find_trade_date(self) -> str:
        """找最近一个 index_global 中有 HSI 数据的交易日（最多回溯 4 天）"""
        today = datetime.now()
        for delta in range(5):
            d = (today - timedelta(days=delta)).strftime("%Y%m%d")
            try:
                df = self.pro.query("index_global", trade_date=d)
                if df is not None and not df.empty and "HSI" in df["ts_code"].values:
                    return d
            except Exception:
                continue
        return today.strftime("%Y%m%d")

    def get_index_quotes(self) -> list[dict]:
        """港股主要指数行情（index_global 接口）"""
        rows = []
        try:
            df = self.pro.query("index_global", trade_date=self.trade_date)
            if df is None or df.empty:
                return [{"名称": name, "error": "无数据"} for name, _ in HK_INDEX_CODES]
            for name, ts_code in HK_INDEX_CODES:
                matched = df[df["ts_code"] == ts_code]
                if matched.empty:
                    rows.append({"名称": name, "error": "代码未找到"})
                    continue
                r = matched.iloc[0]
                pct = r.get("pct_chg")
                chg = r.get("change")
                rows.append({
                    "名称":      name,
                    "最新价":    round(float(r["close"]), 2),
                    "涨跌幅(%)": round(float(pct), 2) if pct is not None else None,
                    "涨跌点":    round(float(chg), 2)  if chg is not None else None,
                    "交易日期":  str(r["trade_date"]),
                })
        except Exception as e:
            rows = [{"名称": name, "error": str(e)} for name, _ in HK_INDEX_CODES]
        return rows

    def collect_all(self) -> dict:
        result: dict = {"trade_date": self.trade_date}
        try:
            result["index_quotes"] = self.get_index_quotes()
        except Exception as e:
            result["index_quotes"] = {"error": str(e)}
        return result


if __name__ == "__main__":
    collector = HKStockCollector()
    print(f"\n{'='*40}")
    print(f" 港股指数日报 | {collector.report_date}  交易日: {collector.trade_date}")
    print(f"{'='*40}")

    idx = collector.get_index_quotes()
    print("\n[主要指数]")
    for item in idx:
        if "error" in item:
            print(f"  ▸ {item['名称']:<8} [失败] {item['error']}")
        else:
            pct = item["涨跌幅(%)"]
            sign = "+" if pct and pct >= 0 else ""
            print(f"  ▸ {item['名称']:<8}  {item['最新价']:>10.2f}  {sign}{pct}%  ({sign}{item.get('涨跌点', 'N/A')}pt)")
