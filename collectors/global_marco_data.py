"""全球宏观市场核心指标采集

数据源：
  A股指数     — Tushare Pro  index_daily（无需代理）
  其余所有    — yfinance（需走代理，由 main.py network_context 统一注入）

collect_all() 返回结构：
    {
        "A股":      [{"名称", "最新价", "涨跌幅(%)", "交易日期"}, ...],
        "美股":     [...],
        "宏观利率": [...],   # 美债、美元指数、VIX、CNY
        "港股&欧亚": [...],
        "大宗商品": [...],   # 黄金、原油、比特币
    }
"""
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro

# ── A股指数（Tushare ts_code）──────────────────────────────────────────
A_SHARE_INDICES: list[tuple[str, str]] = [
    ("上证指数", "000001.SH"),
    ("深证成指", "399001.SZ"),
    ("沪深300",  "000300.SH"),
    ("创业板指", "399006.SZ"),
    ("中证500",  "000905.SH"),
    ("科创50",   "000688.SH"),
]

# ── 境外市场（yfinance ticker）─────────────────────────────────────────
US_INDICES: list[tuple[str, str]] = [
    ("标普500(期货)",  "ES=F"),    # ^GSPC 在当前Yahoo版本无数据，用期货代替
    ("纳斯达克(期货)", "NQ=F"),    # ^IXIC 同上
    ("道琼斯",        "^DJI"),
]

MACRO_RATES: list[tuple[str, str]] = [
    ("美债10Y(%)",  "^TNX"),
    ("美元指数",    "DX-Y.NYB"),
    ("VIX恐慌指数", "^VIX"),
    ("美元兑人民币", "CNY=X"),
]

HK_EU_INDICES: list[tuple[str, str]] = [
    ("恒生指数",   "^HSI"),
    ("恒生科技",   "3032.HK"),   # ^HSTECH Yahoo不支持，用ETF代替
    ("日经225",    "^N225"),
    ("德国DAX",    "^GDAXI"),
    ("英国富时100", "^FTSE"),
]

COMMODITIES: list[tuple[str, str]] = [
    ("纽约黄金",  "GC=F"),
    ("布伦特原油", "BZ=F"),
    ("WTI原油",   "CL=F"),
    ("比特币",    "BTC-USD"),
]


def _yf_row(name: str, ticker: str) -> dict:
    """用 yfinance 获取单个品种最新行情。"""
    hist = yf.Ticker(ticker).history(period="5d")
    if hist.empty:
        return {"名称": name, "error": "无数据"}
    close = float(hist["Close"].iloc[-1])
    prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
    pct   = round((close - prev) / prev * 100, 2) if prev else None
    return {
        "名称":     name,
        "最新价":   round(close, 4),
        "涨跌幅(%)": pct,
        "交易日期": hist.index[-1].strftime("%Y-%m-%d"),
    }


def _yf_group(pairs: list[tuple[str, str]]) -> list[dict]:
    rows = []
    for name, ticker in pairs:
        try:
            rows.append(_yf_row(name, ticker))
        except Exception as e:
            rows.append({"名称": name, "error": str(e)})
    return rows


class GlobalIndexCollector:
    def __init__(self):
        self.pro = get_pro()
        self._a_trade_date: str | None = None

    def _latest_a_trade_date(self) -> str:
        if self._a_trade_date:
            return self._a_trade_date
        today = datetime.now().strftime("%Y%m%d")
        df = self.pro.trade_cal(exchange="SSE", end_date=today, is_open="1", limit=1)
        self._a_trade_date = df.iloc[0]["cal_date"]
        return self._a_trade_date

    def get_a_share_indices(self) -> list[dict]:
        trade_date = self._latest_a_trade_date()
        rows = []
        for name, ts_code in A_SHARE_INDICES:
            try:
                df = self.pro.index_daily(ts_code=ts_code, trade_date=trade_date)
                if df is None or df.empty:
                    df = self.pro.index_daily(ts_code=ts_code, limit=1)
                if df is None or df.empty:
                    rows.append({"名称": name, "error": "无数据"})
                    continue
                r = df.iloc[0]
                pct = round(float(r["pct_chg"]), 2) if r["pct_chg"] is not None else None
                rows.append({
                    "名称":     name,
                    "最新价":   round(float(r["close"]), 2),
                    "涨跌幅(%)": pct,
                    "交易日期": str(r["trade_date"]),
                })
            except Exception as e:
                rows.append({"名称": name, "error": str(e)})
        return rows

    def collect_all(self) -> dict:
        result: dict = {}
        tasks = [
            ("A股",      self.get_a_share_indices),
            ("美股",      lambda: _yf_group(US_INDICES)),
            ("宏观利率",  lambda: _yf_group(MACRO_RATES)),
            ("港股&欧亚", lambda: _yf_group(HK_EU_INDICES)),
            ("大宗商品",  lambda: _yf_group(COMMODITIES)),
        ]
        for key, fn in tasks:
            try:
                result[key] = fn()
            except Exception as e:
                result[key] = {"error": str(e)}
        return result


# 保留旧类名，main.py 引用不变
class GlobalMacroCollector(GlobalIndexCollector):
    pass


if __name__ == "__main__":
    collector = GlobalIndexCollector()
    data = collector.collect_all()

    for market, rows in data.items():
        print(f"\n【{market}】")
        if isinstance(rows, dict):
            print(f"  [错误] {rows.get('error')}")
            continue
        for item in rows:
            if "error" in item:
                print(f"  {item['名称']:<14} [失败] {item['error']}")
            else:
                pct = item["涨跌幅(%)"]
                sign = "+" if pct and pct > 0 else ""
                pct_str = f"{sign}{pct}%" if pct is not None else "N/A"
                print(f"  {item['名称']:<14} {item['最新价']:>12.4f}  {pct_str:>8}  {item['交易日期']}")
