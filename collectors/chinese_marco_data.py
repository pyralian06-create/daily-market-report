import akshare as ak
import pandas as pd
import datetime

class ChinaMacroCollector:
    def __init__(self):
        # 结果存储
        self.report_date = datetime.date.today().strftime('%Y-%m-%d')
        self.data = {}

    def _get_latest_row(self, df):
        """通用：获取 DataFrame 的最后一行"""
        if df is not None and not df.empty:
            return df.iloc[-1]
        return None

    def collect_all(self):
        print(f"开始采集宏观数据 (报告日期: {self.report_date})...")
        
        # 1. 货币供应量 (M1/M2) - 核心：M2同比增长 & M1-M2剪刀差
        try:
            df = ak.macro_china_money_supply()
            latest = self._get_latest_row(df)
            self.data['money_supply'] = {
                "指标名称": "货币供应量",
                "统计时间": latest['月份'],
                "M2同比增长": f"{latest['货币和准货币(M2)-同比增长']}%",
                "M1同比增长": f"{latest['货币(M1)-同比增长']}%",
                "意义": "观察市场总水量及流动性活性"
            }
        except Exception as e: print(f"M2采集失败: {e}")

        # 2. 社会融资规模 (社融) - 核心：增量当月值
        try:
            df = ak.macro_china_shrzgm()
            latest = self._get_latest_row(df)
            self.data['social_financing'] = {
                "指标名称": "社融增量",
                "统计月份": latest['月份'],
                "当月增量": f"{latest['社会融资规模增量']} 亿元",
                "意义": "实体经济真实的融资需求"
            }
        except Exception as e: print(f"社融采集失败: {e}")

        # 3. 贷款市场报价利率 (LPR) - 核心：5年期利率
        try:
            df = ak.macro_china_lpr()
            latest = self._get_latest_row(df)
            self.data['lpr'] = {
                "指标名称": "LPR利率",
                "发布日期": latest['TRADE_DATE'],
                "1年期": f"{latest['LPR1Y']}%",
                "5年期以上": f"{latest['LPR5Y']}%",
                "意义": "资金成本，影响房贷和基建"
            }
        except Exception as e: print(f"LPR采集失败: {e}")

        # 4. 采购经理指数 (PMI) - 核心：50荣枯线
        try:
            df = ak.macro_china_pmi()
            latest = self._get_latest_row(df)
            self.data['pmi'] = {
                "指标名称": "PMI",
                "统计月份": latest['月份'],
                "制造业指数": latest['制造业-指数'],
                "非制造业指数": latest['非制造业-指数'],
                "状态": "扩张" if latest['制造业-指数'] > 50 else "收缩",
                "意义": "经济先行指标，50为荣枯分水岭"
            }
        except Exception as e: print(f"PMI采集失败: {e}")

        # 5. 消费者价格指数 (CPI) - 核心：同比变化
        try:
            df = ak.macro_china_cpi()
            latest = self._get_latest_row(df)
            self.data['cpi'] = {
                "指标名称": "CPI",
                "统计月份": latest['月份'],
                "全国同比": f"{latest['全国-同比增长']}%",
                "意义": "通胀水平，影响货币政策转向"
            }
        except Exception as e: print(f"CPI采集失败: {e}")

        # 6. 宏观杠杆率 (国家资产负债表数据)
        try:
            df = ak.macro_cnbs()
            latest = self._get_latest_row(df)
            self.data['leverage'] = {
                "指标名称": "宏观杠杆率",
                "统计年份": latest['年份'],
                "居民部门": f"{latest['居民部门']}%",
                "非金融企业部门": f"{latest['非金融企业部门']}%",
                "政府部门": f"{latest['政府部门']}%",
                "意义": "债务压力与去杠杆风险监控"
            }
        except Exception as e: print(f"杠杆率采集失败: {e}")

        return self.data

    def format_print(self):
        """格式化输出，用于日报展示"""
        print("\n" + "="*50)
        print(f"中国宏观核心数据快报 - {self.report_date}")
        print("="*50)
        for key, info in self.data.items():
            print(f"【{info['指标名称']}】")
            for k, v in info.items():
                if k not in ['指标名称', '意义']:
                    print(f"  - {k}: {v}")
            print(f"  * 研判: {info['意义']}")
            print("-" * 30)

if __name__ == "__main__":
    collector = ChinaMacroCollector()
    collector.collect_all()
    collector.format_print()