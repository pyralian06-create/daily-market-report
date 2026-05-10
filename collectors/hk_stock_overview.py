"""港股行情采集

数据源：Tushare Pro
  index_global — 全球指数行情（含 HSI / HKTECH / HSHKCI）
  hk_daily     — 港股个股日行情（全市场快照，用于广度分析）
  hk_tradecal  — 港股交易日历

hk_daily.amount 单位为港元（HKD），转亿港元需除以 1e8。

collect_all() 返回结构：
    {
        "trade_date":     "20260508",
        "index_quotes":   [{"名称", "最新价", "涨跌幅(%)", "涨跌点"}, ...],
        "market_breadth": {
            "上涨家数", "下跌家数", "平盘家数",
            "上涨家数环比", "下跌家数环比",
            "总成交额(亿港元)", "成交额环比(%)",
            "市场平均涨幅", "强势股占比", "弱势股占比",
        },
    }
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro

# hk_daily.amount 单位：港元 → 亿港元
_AMOUNT_HKD_TO_YI = 1e8

HK_INDEX_CODES: list[tuple[str, str]] = [
    ("恒生指数",  "HSI"),
    ("恒生科技",  "HKTECH"),
    ("恒生综合",  "HSHKCI"),
]


def _get_hk_trade_dates(pro) -> tuple[str, str | None]:
    """一次性获取最近两个港股交易日（当日、昨日），使用 hk_tradecal 接口"""
    today = datetime.now().strftime("%Y%m%d")
    df = pro.hk_tradecal(end_date=today, is_open="1", limit=2)
    if df is None or df.empty:
        raise RuntimeError("hk_tradecal 返回空数据，无法获取港股交易日历")
    df = df.sort_values("cal_date", ascending=False)
    curr = str(df.iloc[0]["cal_date"])
    prev = str(df.iloc[1]["cal_date"]) if len(df) >= 2 else None
    return curr, prev


class HKStockCollector:
    def __init__(self):
        self.pro = get_pro()
        self.trade_date, self.prev_trade_date = _get_hk_trade_dates(self.pro)
        self.report_date = datetime.now().strftime("%Y-%m-%d")
        self._full_df: pd.DataFrame | None = None
        self._prev_df: pd.DataFrame | None = None

    def _load_daily(self) -> None:
        if self._full_df is None:
            df = self.pro.hk_daily(trade_date=self.trade_date)
            if df is not None and not df.empty:
                df = df.copy()
                df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
                df["amount"]  = pd.to_numeric(df["amount"],  errors="coerce")
                self._full_df = df

        if self._prev_df is None and self.prev_trade_date:
            df = self.pro.hk_daily(trade_date=self.prev_trade_date)
            if df is not None and not df.empty:
                df = df.copy()
                df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
                df["amount"]  = pd.to_numeric(df["amount"],  errors="coerce")
                self._prev_df = df

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

    def get_market_breadth(self) -> dict:
        """港股全市场广度（含与昨日对比）"""
        self._load_daily()
        if self._full_df is None:
            return {"error": "hk_daily 数据为空"}

        df = self._full_df
        advance = int((df["pct_chg"] > 0).sum())
        decline = int((df["pct_chg"] < 0).sum())
        flat    = int((df["pct_chg"] == 0).sum())
        total_turnover = df["amount"].sum() / _AMOUNT_HKD_TO_YI
        avg_pct   = round(float(df["pct_chg"].mean()), 2)
        strong    = round((df["pct_chg"] > 3).sum() / len(df) * 100, 2)
        weak      = round((df["pct_chg"] < -3).sum() / len(df) * 100, 2)

        result: dict = {
            "交易日期":        self.trade_date,
            "上涨家数":        advance,
            "下跌家数":        decline,
            "平盘家数":        flat,
            "总成交额(亿港元)": round(total_turnover, 2),
            "市场平均涨幅":    f"{avg_pct}%",
            "强势股占比(>3%)": f"{strong}%",
            "弱势股占比(<-3%)": f"{weak}%",
            "上涨家数环比":    None,
            "下跌家数环比":    None,
            "成交额环比(%)":   None,
        }

        if self._prev_df is not None:
            pv = self._prev_df
            prev_advance  = int((pv["pct_chg"] > 0).sum())
            prev_decline  = int((pv["pct_chg"] < 0).sum())
            prev_turnover = pv["amount"].sum() / _AMOUNT_HKD_TO_YI

            result["上涨家数环比"]  = advance - prev_advance
            result["下跌家数环比"]  = decline - prev_decline
            if prev_turnover > 0:
                result["成交额环比(%)"] = round(
                    (total_turnover - prev_turnover) / prev_turnover * 100, 2
                )

        return result

    def collect_all(self) -> dict:
        result: dict = {"trade_date": self.trade_date}
        tasks = [
            ("index_quotes",   self.get_index_quotes),
            ("market_breadth", self.get_market_breadth),
        ]
        for key, fn in tasks:
            try:
                result[key] = fn()
            except Exception as e:
                result[key] = {"error": str(e)}
        return result


if __name__ == "__main__":
    collector = HKStockCollector()
    print(f"\n{'='*40}")
    print(f" 港股核心指标日报 | {collector.report_date}  交易日: {collector.trade_date}")
    print(f"{'='*40}")

    idx = collector.get_index_quotes()
    print("\n[1. 主要指数]")
    for item in idx:
        if "error" in item:
            print(f"  ▸ {item['名称']:<8} [失败] {item['error']}")
        else:
            pct = item["涨跌幅(%)"]
            sign = "+" if pct and pct >= 0 else ""
            print(f"  ▸ {item['名称']:<8}  {item['最新价']:>10.2f}  {sign}{pct}%  ({sign}{item.get('涨跌点', 'N/A')}pt)")

    breadth = collector.get_market_breadth()
    print("\n[2. 市场广度]")
    if "error" in breadth:
        print(f"  [失败] {breadth['error']}")
    else:
        adv_delta = breadth["上涨家数环比"]
        dec_delta = breadth["下跌家数环比"]
        to_delta  = breadth["成交额环比(%)"]
        adv_str = f" ({'+' if adv_delta and adv_delta>=0 else ''}{adv_delta})" if adv_delta is not None else ""
        dec_str = f" ({'+' if dec_delta and dec_delta>=0 else ''}{dec_delta})" if dec_delta is not None else ""
        to_str  = f" ({'+' if to_delta and to_delta>=0 else ''}{to_delta}%)" if to_delta is not None else ""
        print(f"  ▸ 涨跌家数 : {breadth['上涨家数']}{adv_str} 涨 / {breadth['下跌家数']}{dec_str} 跌 / {breadth['平盘家数']} 平")
        print(f"  ▸ 总成交额 : {breadth['总成交额(亿港元)']} 亿港元{to_str}")
        print(f"  ▸ 市场均涨 : {breadth['市场平均涨幅']}  强势: {breadth['强势股占比(>3%)']}  弱势: {breadth['弱势股占比(<-3%)']}")
    print()
