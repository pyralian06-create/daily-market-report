import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

# ==========================================
# 1. 配置网络代理 (解决 TLS connect error)
# 请根据你的实际代理软件修改端口，例如 Clash 是 7890，v2ray 是 10809
# ==========================================
PROXY_URL = "http://127.0.0.1:7897" 

# 方案 A：全局注入环境变量 (对大部分底层 HTTP 库都有效)
os.environ['http_proxy'] = PROXY_URL
os.environ['https_proxy'] = PROXY_URL
os.environ['ALL_PROXY'] = PROXY_URL

def get_global_macro_market():
    """获取隔夜全球宏观市场核心指标"""
    tickers = {
        "US_10Y_Yield": "^TNX",      # 10年期美债
        "Dollar_Index": "DX-Y.NYB",  # 美元指数
        "VIX_Fear_Index": "^VIX",    # 恐慌指数
        "S&P_500": "^GSPC",          # 标普500
        "Nasdaq": "^IXIC",           # 纳斯达克
        "Dow_Jones": "^DJI",         # 道琼斯
        "USD_CNY": "CNY=X",          # 在岸人民币
        "Hang_Seng": "^HSI",         # 恒生指数
        "China_Internet": "KWEB",    # 中概互联网ETF
        "Gold_Futures": "GC=F",      # 黄金期货
        "Crude_Oil": "CL=F",         # WTI原油期货
        "Bitcoin": "BTC-USD"         # 比特币
    }
    
    # 获取当前日期和 10 天前的日期，用于显式指定范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    macro_data = {}
    for name, ticker in tickers.items():
        try:
            stock = yf.Ticker(ticker)
            
            hist = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval="1d"
            )

            print(f"{name}:{hist}")
            
            if len(hist) >= 2:
                last_close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                pct_change = ((last_close - prev_close) / prev_close) * 100
                macro_data[name] = {"value": round(last_close, 4), "pct_change": round(pct_change, 2)}
            else:
                macro_data[name] = {"value": "数据不足", "pct_change": "N/A"}
                
        except Exception as e:
            # 统一错误状态的数据结构，避免外部遍历时发生 TypeError
            macro_data[name] = {"value": "网络异常", "pct_change": "N/A"}
            # 可以选择打印底层报错方便调试，生产环境可以注释掉
            print(f"  [Log] {name} 抓取失败: {str(e).splitlines()[0]}") 
            
    return macro_data

if __name__ == "__main__":
    global_metrics = get_global_macro_market()
    
    print("\n" + "="*40)
    print(" 隔夜全球宏观市场前瞻")
    print("="*40)
    
    for metric, data in global_metrics.items():
        # 增加一个格式化处理，让异常数据也能优雅打印
        if data['pct_change'] == "N/A":
            print(f"[{metric:<15}]: {data['value']}")
        else:
            # 涨跌幅带上正负号会更直观
            sign = "+" if data['pct_change'] > 0 else ""
            print(f"[{metric:<15}]: {data['value']:<8} (涨跌幅: {sign}{data['pct_change']}%)")
    print("\n")