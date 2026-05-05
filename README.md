# Daily Market Report

每日自动采集全球金融市场数据，生成晨报 / 晚报，附带 AI 市场解读，推送至 Telegram。

## 功能概览

| 报告 | 触发时间 | 数据内容 |
|------|----------|----------|
| 晨报 | 09:00 (Asia/Shanghai) | 全球指数行情、国债 / 利率体系、财经资讯头条 |
| 晚报 | 17:00 (Asia/Shanghai) | A 股行情（市场广度 / 行业板块 / 沪深港通 / 两融）、中国宏观数据、财经资讯头条 |

每份报告末尾附有 **Gemini AI 市场解读**（中文，400–600 字），报告同时保存为本地文件。

---

## 项目结构

```
.
├── main.py                  # CLI 入口（--morning / --evening / --send）
├── scheduler.py             # 定时调度守护进程（schedule 库）
├── settings.py              # 统一配置入口，从 .env 加载
├── tushare_client.py        # Tushare Pro API 单例工厂
├── collectors/
│   ├── a_stock_overview.py      # A 股：市场广度 / 行业资金流 / 沪深港通 / 两融
│   ├── chinese_marco_data.py    # 中国宏观：M2 / CPI / PPI / PMI / LPR / GDP / 社融
│   ├── global_marco_data.py     # 全球指数：A 股(Tushare) + 美欧港股 / 大宗(yfinance)
│   ├── global_economy_data.py   # 利率体系：美债 / T-bill / LIBOR / SHIBOR / HIBOR
│   └── rss_news_collector.py    # 财经资讯：RSS 多源抓取
├── reporters/
│   ├── morning_formatter.py     # 晨报格式化
│   ├── evening_formatter.py     # 晚报格式化
│   └── ai_summarizer.py         # Gemini AI 摘要生成
├── senders/
│   └── telegram_sender.py       # Telegram Bot 推送（HTML 模式，自动分块）
├── reports/                 # 生成的报告文件（YYYY-MM-DD_morning/evening.txt）
├── logs/                    # scheduler 运行日志
├── .env.example             # 环境变量模板
└── requirements.txt
```

---

## 数据源

| 数据 | 来源 |
|------|------|
| A 股指数 / 行业资金流 / 两融 / 沪深港通 / 中国宏观 / 利率 | [Tushare Pro](https://tushare.pro) |
| 美股 / 港股 / 欧股 / 大宗商品 / 汇率 | [yfinance](https://github.com/ranaroussi/yfinance) |
| 财经资讯 | RSS（东方财富研报、华尔街见闻等） |
| AI 摘要 | Google Gemini (`gemini-3-flash-preview`) |

---

## 环境配置

```bash
cp .env.example .env
```

编辑 `.env`，填入以下变量：

```
TUSHARE_TOKEN=       # Tushare Pro token
TUSHARE_URL=         # Tushare 自定义 API 地址（可选）
TELEGRAM_BOT_TOKEN=  # Telegram Bot token（@BotFather 获取）
TELEGRAM_CHAT_ID=    # 目标 chat ID（@userinfobot 获取）
GOOGLE_API_KEY=      # Google AI Studio API Key（AI 摘要可选）
```

---

## 安装与运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**手动生成并打印报告：**
```bash
python main.py --morning          # 晨报（打印到终端）
python main.py --evening          # 晚报（打印到终端）
```

**生成并推送到 Telegram：**
```bash
python main.py --morning --send
python main.py --evening --send
```

**启动定时调度（09:00 晨报 / 17:00 晚报，自动发送）：**
```bash
python scheduler.py
# 后台运行：
nohup python scheduler.py > logs/scheduler.log 2>&1 &
```

报告文件自动保存至 `reports/YYYY-MM-DD_morning.txt` / `reports/YYYY-MM-DD_evening.txt`，重复触发时覆盖。

---

## 注意事项

- `.env` 已加入 `.gitignore`，不会提交到版本库
- `GOOGLE_API_KEY` 未配置时 AI 摘要自动跳过，不影响报告生成与推送
- yfinance 需要能访问 Yahoo Finance（境外网络或代理）
- Tushare 部分接口（LIBOR / HIBOR）数据已停更，字段保留但数值可能陈旧
