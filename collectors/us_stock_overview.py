"""美股行情采集

数据源：Tushare Pro
  us_tradecal  — 美股交易日历
  index_global — 全球指数行情（含 SPX / DJI）
  us_daily     — 美股个股日行情（全市场快照，用于广度分析）

us_daily.amount 单位待确认（可能为美元）。
当前按美元处理，除以 1e8 转亿美元；__main__ 打印原始 sum 供人工核实。

collect_all() 返回结构：
    {
        "trade_date":     "20260508",
        "index_quotes":   [{"名称", "最新价", "涨跌幅(%)", "涨跌点"}, ...],
        "market_breadth": {
            "上涨家数", "下跌家数", "平盘家数",
            "上涨家数环比", "下跌家数环比",
            "总成交额(亿美元)", "成交额环比(%)",
            "市场平均涨幅", "强势股占比(>3%)", "弱势股占比(<-3%)",
        },
    }
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro

# us_daily.amount 单位：美元（待核实）→ 亿美元
_AMOUNT_USD_TO_YI = 1e8

US_INDEX_CODES: list[tuple[str, str]] = [
    ("标普500", "SPX"),
    ("道琼斯",  "DJI"),
]


def _get_us_trade_dates(pro) -> tuple[str, str | None]:
    """获取最近两个有 index_global 数据的美股交易日（处理未到开盘时间的情况）"""
    today = datetime.now().strftime("%Y%m%d")
    df = pro.us_tradecal(end_date=today, is_open="1", limit=10)
    if df is None or df.empty:
        raise RuntimeError("us_tradecal 返回空数据，无法获取美股交易日历")
    df = df.sort_values("cal_date", ascending=False)
    dates = [str(d) for d in df["cal_date"]]

    # 找到最近两个有 SPX index_global 数据的交易日
    found: list[str] = []
    for d in dates:
        chk = pro.query("index_global", trade_date=d)
        if chk is not None and not chk.empty and "SPX" in chk["ts_code"].values:
            found.append(d)
            if len(found) == 2:
                break

    if len(found) >= 2:
        return found[0], found[1]
    if len(found) == 1:
        return found[0], None
    return dates[0], dates[1] if len(dates) >= 2 else (dates[0], None)


class USStockCollector:
    def __init__(self):
        self.pro = get_pro()
        self.trade_date, self.prev_trade_date = _get_us_trade_dates(self.pro)
        self.report_date = datetime.now().strftime("%Y-%m-%d")
        self._full_df: pd.DataFrame | None = None
        self._prev_df: pd.DataFrame | None = None

    def _load_daily(self) -> None:
        if self._full_df is None:
            df = self.pro.us_daily(trade_date=self.trade_date)
            if df is not None and not df.empty:
                df = df.copy()
                df["pct_change"] = pd.to_numeric(df["pct_change"], errors="coerce")
                df["amount"]  = pd.to_numeric(df["amount"],  errors="coerce")
                self._full_df = df

        if self._prev_df is None and self.prev_trade_date:
            df = self.pro.us_daily(trade_date=self.prev_trade_date)
            if df is not None and not df.empty:
                df = df.copy()
                df["pct_change"] = pd.to_numeric(df["pct_change"], errors="coerce")
                df["amount"]  = pd.to_numeric(df["amount"],  errors="coerce")
                self._prev_df = df

    def get_index_quotes(self) -> list[dict]:
        """美股主要指数行情（index_global 接口）"""
        rows = []
        try:
            df = self.pro.query("index_global", trade_date=self.trade_date)
            if df is None or df.empty:
                return [{"名称": name, "error": "无数据"} for name, _ in US_INDEX_CODES]
            for name, ts_code in US_INDEX_CODES:
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
            rows = [{"名称": name, "error": str(e)} for name, _ in US_INDEX_CODES]
        return rows

    def get_market_breadth(self) -> dict:
        """美股全市场广度（含与昨日对比）"""
        self._load_daily()
        if self._full_df is None:
            return {"error": "us_daily 数据为空"}

        df = self._full_df
        advance = int((df["pct_change"] > 0).sum())
        decline = int((df["pct_change"] < 0).sum())
        flat    = int((df["pct_change"] == 0).sum())
        total_turnover = df["amount"].sum() / _AMOUNT_USD_TO_YI
        avg_pct   = round(float(df["pct_change"].mean()), 2)
        strong    = round((df["pct_change"] > 3).sum() / len(df) * 100, 2)
        weak      = round((df["pct_change"] < -3).sum() / len(df) * 100, 2)

        result: dict = {
            "交易日期":           self.trade_date,
            "上涨家数":           advance,
            "下跌家数":           decline,
            "平盘家数":           flat,
            "总成交额(亿美元)":   round(total_turnover, 2),
            "市场平均涨幅":       f"{avg_pct}%",
            "强势股占比(>3%)":    f"{strong}%",
            "弱势股占比(<-3%)":   f"{weak}%",
            "上涨家数环比":       None,
            "下跌家数环比":       None,
            "成交额环比(%)":      None,
        }

        if self._prev_df is not None:
            pv = self._prev_df
            prev_advance  = int((pv["pct_change"] > 0).sum())
            prev_decline  = int((pv["pct_change"] < 0).sum())
            prev_turnover = pv["amount"].sum() / _AMOUNT_USD_TO_YI

            result["上涨家数环比"] = advance - prev_advance
            result["下跌家数环比"] = decline - prev_decline
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
    import json

    collector = USStockCollector()
    print(f"\n{'='*40}")
    print(f" 美股核心指标日报 | {collector.report_date}  交易日: {collector.trade_date}")
    print(f"{'='*40}\n")

    # 打印原始 amount sum 供单位核实
    collector._load_daily()
    if collector._full_df is not None:
        raw_sum = collector._full_df["amount"].sum()
        print(f"[调试] us_daily amount 原始总和: {raw_sum:.2f}  (÷1e8 = {raw_sum/1e8:.2f} 亿)\n")

    data = collector.collect_all()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print()
