import akshare as ak
from datetime import datetime


# ==========================================
# 2. 数据采集服务类
# ==========================================
class DailyMarketCollector:
    def __init__(self):
        self.report_date = datetime.now().strftime("%Y-%m-%d")

    def get_market_breadth(self):
        """计算市场广度与流动性 (基于 Mock 的全市场数据)"""
        df_spot = ak.stock_zh_a_spot_em()
        
        # 统计涨跌平家数
        advance = len(df_spot[df_spot["涨跌幅"] > 0])
        decline = len(df_spot[df_spot["涨跌幅"] < 0])
        flat = len(df_spot[df_spot["涨跌幅"] == 0])
        limit_up = len(df_spot[df_spot["涨跌幅"] >= 9.9])
        limit_down = len(df_spot[df_spot["涨跌幅"] <= -9.9])
        
        # 统计两市总成交额 (转换为 亿元)
        total_turnover = df_spot["成交额"].sum() / 100_000_000
        
        return {
            "总成交额(亿元)": round(total_turnover, 2),
            "上涨家数": advance,
            "下跌家数": decline,
            "平盘家数": flat,
            "涨停家数": limit_up,
            "跌停家数": limit_down
        }
    

    def get_sector_fund_flow(self, top_n: int = 5):
        """获取行业主力资金流向排行 (真实接口调用)"""
        print("Fetching `stock_sector_fund_flow_rank`...")
        try:
            # 获取今日行业资金流向排行
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")

            # 确保按主力净流入降序排列 (通常接口默认是降序，保险起见排一下)
            df_sorted = df.sort_values(by="今日主力净流入-净额", ascending=False)

            # 提取前 top_n 名净流入最多的行业，并加入"主力净流入最大股"
            top_inflow = df_sorted.head(top_n)[["名称", "今日主力净流入-净额", "今日涨跌幅", "今日主力净流入最大股"]]

            # 将主力净流入净额(元)转换为亿元，保留两位小数
            top_inflow["主力净流入(亿元)"] = (top_inflow["今日主力净流入-净额"] / 100_000_000).round(2)

            return top_inflow[["名称", "主力净流入(亿元)", "今日涨跌幅", "今日主力净流入最大股"]].to_dict(orient="records")
            
        except Exception as e:
            return f"资金流向提取异常: {e}"

    def get_margin_balance(self):
        """获取沪深两市最新的两融余额汇总 (真实接口调用)"""
        print("Fetching SH and SZ margin data...")
        try:
            # 1. 分别获取沪深两市两融历史数据
            df_sh = ak.macro_china_market_margin_sh()
            df_sz = ak.macro_china_market_margin_sz()
            
            # 2. 提取最新一天的数据 (通常是 T-1 日更新)
            latest_sh = df_sh.iloc[-1]
            latest_sz = df_sz.iloc[-1]
            
            # 3. 字段单位默认是"元"，这里转换为"亿元"
            sh_balance = latest_sh['融资融券余额'] / 100_000_000
            sz_balance = latest_sz['融资融券余额'] / 100_000_000
            total_balance = sh_balance + sz_balance
            
            return {
                "交易日期": latest_sh['日期'], 
                "沪市余额(亿元)": round(sh_balance, 2),
                "深市余额(亿元)": round(sz_balance, 2),
                "两融总余额(亿元)": round(total_balance, 2)
            }
        except Exception as e:
            return f"两融余额提取异常: {e}"

# ==========================================
# 3. 运行主函数
# ==========================================
if __name__ == "__main__":
    collector = DailyMarketCollector()
    
    print(f"\n{'='*40}")
    print(f" A股核心指标日报 | {collector.report_date}")
    print(f"{'='*40}")
    
    # 1. 市场广度 (Mock)
    breadth = collector.get_market_breadth()
    print("\n[1. 市场全局情绪 (全量Spot接口运算)]")
    print(f"  ▸ 两市总成交额 : {breadth['总成交额(亿元)']} 亿元")
    print(f"  ▸ 涨跌家数比   : {breadth['上涨家数']} 涨 / {breadth['下跌家数']} 跌 / {breadth['平盘家数']} 平")
    print(f"  ▸ 涨跌停家数   : {breadth['涨停家数']} 涨停 / {breadth['跌停家数']} 跌停")

    # 2. 两融余额 (Real)
    margin = collector.get_margin_balance()
    print("\n[2. 杠杆情绪 (两融余额)]")
    if isinstance(margin, dict):
        print(f"  ▸ 数据更新日期 : {margin['交易日期']}")
        print(f"  ▸ 两融总余额   : {margin['两融总余额(亿元)']} 亿元 (沪: {margin['沪市余额(亿元)']} + 深: {margin['深市余额(亿元)']})")
    else:
        print(f"  ▸ {margin}")

    # 3. 主力资金流向 (Real)
    sector_flow = collector.get_sector_fund_flow(top_n=5)
    print("\n[3. 行业主力资金净流入 Top 5]")
    if isinstance(sector_flow, list):
        for idx, item in enumerate(sector_flow, 1):
            print(f"  {idx}. {item['名称']:<6} | 净流入: {item['主力净流入(亿元)']:>6} 亿 | 涨跌幅: {item['今日涨跌幅']:>5}% | 龙头: {item['今日主力净流入最大股']}")
    else:
        print(f"  ▸ {sector_flow}")
    print("\n")