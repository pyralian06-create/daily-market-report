"""全球经济核心指标采集（数据源：Tushare Pro）

采集两类数据：
  1. 美国国债收益率曲线 — us_tycr
  2. 国际宏观利率体系   — us_tbr / libor / shibor / hibor
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro


def _spread(a, b) -> float | None:
    try:
        return round(float(a) - float(b), 3)
    except (TypeError, ValueError):
        return None


def _rate(val) -> float | None:
    try:
        return round(float(val), 4)
    except (TypeError, ValueError):
        return None


class GlobalEconomyCollector:
    def __init__(self):
        self.pro = get_pro()

    def get_us_treasury_yield(self) -> dict:
        """美国国债收益率曲线（最新一期）"""
        try:
            df = self.pro.us_tycr(limit=1)
            if df is None or df.empty:
                return {"error": "us_tycr 无数据"}
            r = df.iloc[0]
            return {
                "指标": "美国国债收益率",
                "日期": str(r.get("date", "")),
                "2年期(%)": r.get("y2"),
                "10年期(%)": r.get("y10"),
                "30年期(%)": r.get("y30"),
                "10Y-2Y利差(%)": _spread(r.get("y10"), r.get("y2")),
                "意义": "10Y-2Y倒挂警示衰退，10Y上行压制成长股估值",
            }
        except Exception as e:
            return {"error": str(e)}

    def collect_all(self) -> dict:
        result: dict = {}
        tasks = [
            ("us_treasury", self.get_us_treasury_yield),
        ]
        for key, fn in tasks:
            try:
                result[key] = fn()
            except Exception as e:
                result[key] = {"error": str(e)}
        return result


# ═══════════════════════════════════════════════════════════════
# 国际宏观利率体系
# ═══════════════════════════════════════════════════════════════

class IntlMacroCollector:
    """国际宏观利率体系快照。

    覆盖三层利率市场：
      政策层  — 美联储短端利率（us_tbr 隔夜/1M/3M T-bill）+ 国债曲线（us_tycr）
      批发层  — LIBOR USD（全球美元批发融资成本）
      在岸层  — SHIBOR（人民币）/ HIBOR（港元，连接境内外利率）
    """

    def __init__(self):
        self.pro = get_pro()
        self._today = datetime.now().strftime("%Y%m%d")

    def get_us_rates(self) -> dict:
        """美国利率体系：T-bill 短端 + 国债关键期限。"""
        result: dict = {"指标": "美国利率体系"}

        try:
            df = self.pro.us_tbr(limit=1)
            if df is not None and not df.empty:
                r = df.iloc[0]
                result["T-bill日期"] = str(r.get("date", ""))
                result["4W(%)"]  = _rate(r.get("w4_ce"))
                result["3M(%)"]  = _rate(r.get("w13_ce"))
                result["6M(%)"]  = _rate(r.get("w26_ce"))
                result["12M(%)"] = _rate(r.get("w52_ce"))
        except Exception as e:
            result["T-bill_error"] = str(e)

        try:
            df = self.pro.us_tycr(limit=1)
            if df is not None and not df.empty:
                r = df.iloc[0]
                result["国债日期"]      = str(r.get("date", ""))
                result["2Y国债(%)"]     = _rate(r.get("y2"))
                result["10Y国债(%)"]    = _rate(r.get("y10"))
                result["30Y国债(%)"]    = _rate(r.get("y30"))
                result["10Y-2Y利差(%)"] = _spread(r.get("y10"), r.get("y2"))
        except Exception as e:
            result["国债_error"] = str(e)

        result["意义"] = (
            "T-bill短端≈联邦基金利率；10Y-2Y倒挂历史上领先衰退6-18个月；"
            "10Y上行压制成长股估值，美元指数通常同向"
        )
        return result

    def get_libor(self, curr_type: str = "USD") -> dict:
        """LIBOR 各期限利率。"""
        try:
            df = self.pro.libor(curr_type=curr_type, limit=1)
            if df is None or df.empty:
                return {"error": f"libor({curr_type}) 无数据"}
            r = df.iloc[0]
            return {
                "指标":    f"LIBOR {curr_type}",
                "日期":    str(r.get("date", "")),
                "隔夜(%)": _rate(r.get("on")),
                "1W(%)":   _rate(r.get("1w")),
                "1M(%)":   _rate(r.get("1m")),
                "3M(%)":   _rate(r.get("3m")),
                "6M(%)":   _rate(r.get("6m")),
                "12M(%)":  _rate(r.get("12m")),
                "意义":    "3M LIBOR USD 是全球浮动利率贷款/衍生品定价基准",
            }
        except Exception as e:
            return {"error": str(e)}

    def get_shibor(self) -> dict:
        """SHIBOR 各期限利率。"""
        try:
            df = self.pro.shibor(date=self._today)
            if df is None or df.empty:
                df = self.pro.shibor(limit=1)
            if df is None or df.empty:
                return {"error": "shibor 无数据"}
            r = df.iloc[0]
            on = _rate(r.get("on"))
            y1 = _rate(r.get("1y"))
            return {
                "指标":         "SHIBOR",
                "日期":         str(r.get("date", "")),
                "隔夜(%)":      on,
                "1W(%)":        _rate(r.get("1w")),
                "2W(%)":        _rate(r.get("2w")),
                "1M(%)":        _rate(r.get("1m")),
                "3M(%)":        _rate(r.get("3m")),
                "6M(%)":        _rate(r.get("6m")),
                "1Y(%)":        y1,
                "1Y-ON利差(%)": _spread(y1, on),
                "意义":         "隔夜SHIBOR反映短期资金松紧；1Y-隔夜利差扩大暗示收紧预期",
            }
        except Exception as e:
            return {"error": str(e)}

    def get_hibor(self) -> dict:
        """HIBOR 各期限利率。"""
        try:
            df = self.pro.hibor(date=self._today)
            if df is None or df.empty:
                df = self.pro.hibor(limit=1)
            if df is None or df.empty:
                return {"error": "hibor 无数据"}
            r = df.iloc[0]
            return {
                "指标":    "HIBOR",
                "日期":    str(r.get("date", "")),
                "隔夜(%)": _rate(r.get("on")),
                "1W(%)":   _rate(r.get("1w")),
                "1M(%)":   _rate(r.get("1m")),
                "3M(%)":   _rate(r.get("3m")),
                "6M(%)":   _rate(r.get("6m")),
                "1Y(%)":   _rate(r.get("1y")),
                "意义":    "HIBOR 3M 是人民币离岸融资成本，与SHIBOR利差反映跨境资金流动方向",
            }
        except Exception as e:
            return {"error": str(e)}

    def collect_all(self) -> dict:
        result: dict = {}
        tasks = [
            ("us_rates",  self.get_us_rates),
            ("libor_usd", self.get_libor),
            ("shibor",    self.get_shibor),
            ("hibor",     self.get_hibor),
        ]
        for key, fn in tasks:
            try:
                result[key] = fn()
            except Exception as e:
                result[key] = {"error": str(e)}
        return result


if __name__ == "__main__":
    collector = GlobalEconomyCollector()

    print("\n【美国国债收益率】")
    d = collector.get_us_treasury_yield()
    if "error" in d:
        print(f"  [失败] {d['error']}")
    else:
        meaning = d.pop("意义", "")
        d.pop("指标", "")
        for k, v in d.items():
            print(f"  {k:<16} {v}")
        print(f"  → {meaning}")

    print("\n" + "=" * 60)
    print(" 国际宏观利率体系")
    print("=" * 60)
    intl = IntlMacroCollector()

    def _print_rate_dict(d: dict):
        if "error" in d:
            print(f"  [失败] {d['error']}")
            return
        name    = d.pop("指标", "")
        meaning = d.pop("意义", "")
        print(f"  【{name}】")
        for k, v in d.items():
            print(f"    {k:<18} {v}")
        print(f"    → {meaning}")

    _print_rate_dict(intl.get_us_rates())
    _print_rate_dict(intl.get_libor())
    _print_rate_dict(intl.get_shibor())
    _print_rate_dict(intl.get_hibor())
