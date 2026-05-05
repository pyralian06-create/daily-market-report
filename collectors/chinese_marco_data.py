import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tushare_client import get_pro


class ChinaMacroCollector:
    def __init__(self):
        self.pro = get_pro()
        self.report_date = datetime.date.today().strftime("%Y-%m-%d")
        self.data: dict = {}

    def _latest(self, df):
        if df is not None and not df.empty:
            return df.iloc[0]
        return None

    def _collect_money_supply(self):
        """M0/M1/M2 货币供应量"""
        df = self.pro.cn_m(limit=1)
        r = self._latest(df)
        if r is None:
            return
        self.data["money_supply"] = {
            "指标名称": "货币供应量",
            "统计月份": str(r["month"]),
            "M2余额(亿元)": r["m2"],
            "M2同比(%)": r["m2_yoy"],
            "M2环比(%)": r["m2_mom"],
            "M1同比(%)": r["m1_yoy"],
            "M1-M2剪刀差(%)": round(float(r["m1_yoy"]) - float(r["m2_yoy"]), 2),
            "意义": "M2衡量市场总水量，剪刀差反映流动性活性",
        }

    def _collect_social_financing(self):
        """社会融资规模月度增量"""
        df = self.pro.sf_month(limit=1)
        r = self._latest(df)
        if r is None:
            return
        self.data["social_financing"] = {
            "指标名称": "社会融资规模",
            "统计月份": str(r["month"]),
            "当月增量(亿元)": r["inc_month"],
            "累计值(亿元)": r["inc_cumval"],
            "存量(万亿元)": r["stk_endval"],
            "意义": "实体经济真实融资需求，领先信贷扩张",
        }

    def _collect_lpr(self):
        """贷款市场报价利率 LPR"""
        df = self.pro.shibor_lpr(limit=1)
        r = self._latest(df)
        if r is None:
            return
        self.data["lpr"] = {
            "指标名称": "LPR利率",
            "发布日期": str(r["date"]),
            "1年期(%)": r["1y"],
            "5年期以上(%)": r["5y"],
            "意义": "资金成本基准，影响房贷与企业融资",
        }

    def _collect_cpi_ppi(self):
        """CPI / PPI 物价指数"""
        df_cpi = self.pro.cn_cpi(limit=1)
        r = self._latest(df_cpi)
        if r is not None:
            self.data["cpi"] = {
                "指标名称": "CPI",
                "统计月份": str(r["month"]),
                "全国同比(%)": r["nt_yoy"],
                "全国环比(%)": r["nt_mom"],
                "意义": "通胀水平，影响货币政策方向",
            }

        df_ppi = self.pro.cn_ppi(limit=1)
        r = self._latest(df_ppi)
        if r is not None:
            self.data["ppi"] = {
                "指标名称": "PPI",
                "统计月份": str(r["month"]),
                "PPI同比(%)": r["ppi_yoy"],
                "PPI环比(%)": r["ppi_mom"],
                "意义": "工业品出厂价格，传导至CPI的先行指标",
            }

    def _collect_gdp(self):
        """GDP 季度数据"""
        df = self.pro.cn_gdp(limit=1)
        r = self._latest(df)
        if r is None:
            return
        self.data["gdp"] = {
            "指标名称": "GDP",
            "统计季度": str(r["quarter"]),
            "GDP(亿元)": r["gdp"],
            "同比增速(%)": r["gdp_yoy"],
            "第一产业同比(%)": r["pi_yoy"],
            "第二产业同比(%)": r["si_yoy"],
            "第三产业同比(%)": r["ti_yoy"],
            "意义": "经济总量与结构性增速",
        }

    def _collect_pmi(self):
        """PMI 采购经理指数"""
        df = self.pro.cn_pmi(limit=1)
        r = self._latest(df)
        if r is None:
            return
        mfg = float(r["PMI010000"])
        svc = float(r["PMI020100"])
        self.data["pmi"] = {
            "指标名称": "PMI",
            "统计月份": str(r["MONTH"]),
            "制造业PMI": mfg,
            "制造业状态": "扩张" if mfg >= 50 else "收缩",
            "非制造业商务活动": svc,
            "综合PMI产出": float(r["PMI030000"]),
            "意义": "经济先行指标，50为荣枯分水岭",
        }

    def collect_all(self) -> dict:
        print(f"开始采集宏观数据 (报告日期: {self.report_date})...")
        collectors = [
            ("货币供应量 M2", self._collect_money_supply),
            ("社融规模", self._collect_social_financing),
            ("LPR利率", self._collect_lpr),
            ("CPI/PPI", self._collect_cpi_ppi),
            ("GDP", self._collect_gdp),
            ("PMI", self._collect_pmi),
        ]
        for name, fn in collectors:
            try:
                fn()
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ {name} 失败: {e}")
        return self.data

    def format_print(self):
        print("\n" + "=" * 50)
        print(f"中国宏观核心数据快报 - {self.report_date}")
        print("=" * 50)
        for info in self.data.values():
            print(f"【{info['指标名称']}】")
            for k, v in info.items():
                if k not in ("指标名称", "意义"):
                    print(f"  - {k}: {v}")
            print(f"  * 研判: {info['意义']}")
            print("-" * 30)


if __name__ == "__main__":
    collector = ChinaMacroCollector()
    collector.collect_all()
    collector.format_print()
