import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro


def _latest_trade_date() -> str:
    """通过 trade_cal 获取最近一个交易日（YYYYMMDD）"""
    pro = get_pro()
    today = datetime.now().strftime("%Y%m%d")
    df = pro.trade_cal(exchange="SSE", end_date=today, is_open="1", limit=1)
    return df.iloc[0]["cal_date"]


class DailyMarketCollector:
    def __init__(self):
        self.pro = get_pro()
        self.trade_date = _latest_trade_date()
        self.report_date = datetime.now().strftime("%Y-%m-%d")

    def get_market_breadth(self) -> dict:
        """全市场涨跌分布与流动性（daily 接口）"""
        df = self.pro.daily(trade_date=self.trade_date)
        if df is None or df.empty:
            return {"error": "daily 数据为空"}

        advance = int((df["pct_chg"] > 0).sum())
        decline = int((df["pct_chg"] < 0).sum())
        flat = int((df["pct_chg"] == 0).sum())
        limit_up = int((df["pct_chg"] >= 9.9).sum())
        limit_down = int((df["pct_chg"] <= -9.9).sum())
        # amount 单位：千元 → 亿元
        total_turnover = df["amount"].sum() / 10_000

        avg_pct = df["pct_chg"].mean()
        median_pct = df["pct_chg"].median()
        strong_ratio = (df["pct_chg"] > 5).sum() / len(df) * 100
        panic_ratio = (df["pct_chg"] < -5).sum() / len(df) * 100

        denom = df["high"] - df["low"]
        pos = (df["close"] - df["low"]) / denom.replace(0, float("nan"))
        avg_position = pos.mean()

        total_amt = df["amount"].sum()
        top10_amt = df.nlargest(int(len(df) * 0.1), "amount")["amount"].sum()
        concentration = top10_amt / total_amt * 100

        return {
            "交易日期": self.trade_date,
            "总成交额(亿元)": round(total_turnover, 2),
            "上涨家数": advance,
            "下跌家数": decline,
            "平盘家数": flat,
            "涨停家数": limit_up,
            "跌停家数": limit_down,
            "市场平均涨幅": f"{round(avg_pct, 2)}%",
            "涨幅中位数": f"{round(median_pct, 2)}%",
            "强势股占比": f"{round(strong_ratio, 2)}%",
            "大跌股占比": f"{round(panic_ratio, 2)}%",
            "全天重心位置": "高位" if avg_position > 0.6 else ("低位" if avg_position < 0.4 else "中轴"),
            "资金抱团度": f"{round(concentration, 2)}%",
        }

    def get_sector_fund_flow(self, top_n: int = 5) -> dict:
        """行业板块涨跌 Top N（同花顺 moneyflow_ind_ths）"""
        df = self.pro.moneyflow_ind_ths(trade_date=self.trade_date)
        if df is None or df.empty:
            return {"error": "moneyflow_ind_ths 数据为空"}

        df = df.copy()
        df["pct_change"] = df["pct_change"].astype(float)
        df_sorted = df.sort_values("pct_change", ascending=False)

        def _row(r):
            return {
                "板块": r["industry"],
                "涨跌幅(%)": round(float(r["pct_change"]), 2),
                "净流入(百万元)": round(float(r["net_amount"]), 2),
                "成分股数": int(r["company_num"]),
                "领涨股": r["lead_stock"],
                "领涨股涨幅(%)": round(float(r["pct_change_stock"]), 2),
            }

        return {
            f"涨幅前{top_n}": [_row(r) for _, r in df_sorted.head(top_n).iterrows()],
            f"跌幅前{top_n}": [_row(r) for _, r in df_sorted.tail(top_n).sort_values("pct_change").iterrows()],
        }

    def get_margin_balance(self) -> dict:
        """沪深两融余额汇总（margin 接口，各交易所取各自最新一条）"""
        def _latest_for(exchange: str) -> dict:
            df = self.pro.margin(exchange_id=exchange, limit=1)
            if df is None or df.empty:
                return {}
            return df.iloc[0].to_dict()

        sh = _latest_for("SSE")
        sz = _latest_for("SZSE")
        if not sh and not sz:
            return {"error": "margin 数据为空"}

        def _yi(row, col):
            v = row.get(col)
            return round(float(v) / 1e8, 2) if v is not None else None

        sh_bal = _yi(sh, "rzrqye") or 0
        sz_bal = _yi(sz, "rzrqye") or 0
        return {
            "沪市日期": sh.get("trade_date"),
            "深市日期": sz.get("trade_date"),
            "沪市两融余额(亿元)": sh_bal,
            "深市两融余额(亿元)": sz_bal,
            "两融总余额(亿元)": round(sh_bal + sz_bal, 2),
            "沪市融资余额(亿元)": _yi(sh, "rzye"),
            "深市融资余额(亿元)": _yi(sz, "rzye"),
        }

    def get_hsgt_flow(self) -> dict:
        """沪深港通北向/南向资金流向（moneyflow_hsgt）"""
        df = self.pro.moneyflow_hsgt(trade_date=self.trade_date)
        if df is None or df.empty:
            return {"error": "moneyflow_hsgt 数据为空"}

        r = df.iloc[0]
        # 单位：万元 → 亿元
        def _yi(val):
            return round(float(val) / 10_000, 2)

        north = _yi(r["north_money"])
        south = _yi(r["south_money"])
        return {
            "交易日期": self.trade_date,
            "北向资金合计(亿元)": north,
            "沪股通(亿元)": _yi(r["hgt"]),
            "深股通(亿元)": _yi(r["sgt"]),
            "南向资金合计(亿元)": south,
            "港股通(沪)(亿元)": _yi(r["ggt_ss"]),
            "港股通(深)(亿元)": _yi(r["ggt_sz"]),
            "北向情绪": "净流入" if north > 0 else "净流出",
        }

    def collect_all(self) -> dict:
        result = {}
        tasks = [
            ("market_breadth", self.get_market_breadth),
            ("sector_fund_flow", self.get_sector_fund_flow),
            ("margin_balance", self.get_margin_balance),
            ("hsgt_flow", self.get_hsgt_flow),
        ]
        for key, fn in tasks:
            try:
                result[key] = fn()
            except Exception as e:
                result[key] = {"error": str(e)}
        return result


if __name__ == "__main__":
    collector = DailyMarketCollector()
    print(f"\n{'='*40}")
    print(f" A股核心指标日报 | {collector.report_date}  交易日: {collector.trade_date}")
    print(f"{'='*40}")

    breadth = collector.get_market_breadth()
    print("\n[1. 市场全局情绪]")
    print(f"  ▸ 两市总成交额 : {breadth['总成交额(亿元)']} 亿元")
    print(f"  ▸ 涨跌家数比   : {breadth['上涨家数']} 涨 / {breadth['下跌家数']} 跌 / {breadth['平盘家数']} 平")
    print(f"  ▸ 涨跌停家数   : {breadth['涨停家数']} 涨停 / {breadth['跌停家数']} 跌停")
    print(f"  ▸ 平均涨幅     : {breadth['市场平均涨幅']}  中位数: {breadth['涨幅中位数']}")

    margin = collector.get_margin_balance()
    print("\n[2. 杠杆情绪 (两融余额)]")
    print(f"  ▸ 两融总余额   : {margin['两融总余额(亿元)']} 亿元")
    print(f"  ▸ 沪({margin['沪市日期']}): {margin['沪市两融余额(亿元)']}  深({margin['深市日期']}): {margin['深市两融余额(亿元)']}")

    sector = collector.get_sector_fund_flow(top_n=5)
    print("\n[3. 行业板块涨幅 Top5 / 跌幅 Top5]")
    for item in sector.get("涨幅前5", []):
        print(f"  ▸ {item['板块']:<10} {item['涨跌幅(%)']:>6}%  净流入: {item['净流入(百万元)']}百万  领涨: {item['领涨股']} {item['领涨股涨幅(%)']}%")
    print("  ---")
    for item in sector.get("跌幅前5", []):
        print(f"  ▸ {item['板块']:<10} {item['涨跌幅(%)']:>6}%  净流入: {item['净流入(百万元)']}百万  领涨: {item['领涨股']} {item['领涨股涨幅(%)']}%")

    hsgt = collector.get_hsgt_flow()
    print("\n[4. 沪深港通资金流向]")
    print(f"  ▸ 北向资金     : {hsgt['北向资金合计(亿元)']} 亿元 ({hsgt['北向情绪']})  沪股通: {hsgt['沪股通(亿元)']}  深股通: {hsgt['深股通(亿元)']}")
    print(f"  ▸ 南向资金     : {hsgt['南向资金合计(亿元)']} 亿元")
    print()
