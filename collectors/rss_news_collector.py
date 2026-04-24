import feedparser
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

TESTS_DIR = Path(__file__).parent.parent / "tests"


class MarketNewsCollector:
    def __init__(self):
        # 考虑到官方 rsshub.app 国内访问可能受限或被限流，
        # 如果你部署了自己的 RSSHub 实例，可以把这里的 base_url 替换掉
        self.base_url = "https://rsshub.rssforever.com"
        
        # 定义需要采集的 RSS 路由映射
        self.feeds = {
            "【财联社电报】(突发事件/实时情绪)": f"{self.base_url}/cls/depth/1000",
            "【东方财富研报】(机构策略与宏观视点)": f"{self.base_url}/eastmoney/report/strategyreport",
            "【华尔街见闻】 - 最热文章":f"{self.base_url}/wallstreetcn/hot"
        }

    def _clean_html(self, html_content):
        """清洗 RSS 返回的 description 中的 HTML 标签，提取纯文本"""
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    def fetch_feed(self, source_name, url, top_n=10):
        """抓取并解析单个 RSS 源"""
        print(f"正在拉取: {source_name} ...")
        parsed_feed = feedparser.parse(url)

        # 将原始结果写入 tests/ 目录，文件名取 source_name 中的中文/英文部分
        safe_name = re.sub(r"[^\w一-鿿]+", "_", source_name).strip("_")
        TESTS_DIR.mkdir(exist_ok=True)
        debug_path = TESTS_DIR / f"rss_{safe_name}.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(dict(parsed_feed), f, ensure_ascii=False, indent=2, default=str)
        print(f"拉取: {source_name} -> {debug_path}")
        
        # 异常处理：RSSHub 有时会返回状态码错误
        if parsed_feed.bozo and hasattr(parsed_feed.bozo_exception, 'getcode'):
            print(f"  [!] 拉取失败，HTTP 状态码: {parsed_feed.bozo_exception.getcode()}")
            return []

        entries_data = []
        # 只取前 N 条最新资讯
        for entry in parsed_feed.entries[:top_n]:
            # 提取时间 (优先取 pubDate，如果没有则留空)
            pub_date = entry.get("published", "未知时间")
            
            # 提取标题和链接
            title = entry.get("title", "无标题")
            link = entry.get("link", "")
            
            # 提取正文并清洗标签 (财联社的电报内容通常全在 description 里)
            desc_html = entry.get("description", "")
            clean_desc = self._clean_html(desc_html)
            
            # 如果摘要太长，截断它
            if len(clean_desc) > 150:
                clean_desc = clean_desc[:147] + "..."

            entries_data.append({
                "title": title,
                "date": pub_date,
                "desc": clean_desc,
                "link": link
            })
            
        return entries_data

    def generate_report(self, top_n=5):
        """生成 Markdown 格式的资讯聚合报告"""
        report_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        report_lines = []
        report_lines.append(f"# 📢 每日市场情绪与资讯简报")
        report_lines.append(f"**生成时间：** {report_date}")
        report_lines.append("---\n")
        
        for source_name, url in self.feeds.items():
            report_lines.append(f"## {source_name}")
            entries = self.fetch_feed(source_name, url, top_n)
            
            if not entries:
                report_lines.append("> 暂无数据或接口限流。\n")
                continue
                
            for idx, item in enumerate(entries, 1):
                report_lines.append(f"**{idx}. {item['title']}**")
                report_lines.append(f"* {item['date']}")
                # 财联社电报标题和正文可能重复，这里做个简单过滤
                if item['desc'] and item['desc'] not in item['title']:
                    report_lines.append(f"> {item['desc']}")
                report_lines.append("") # 空行分隔
                
            report_lines.append("---\n")
            
        return "\n".join(report_lines)

# ==========================================
# 运行主程序
# ==========================================
if __name__ == "__main__":
    collector = MarketNewsCollector()
    markdown_report = collector.generate_report(top_n=5)
    
    # 打印到控制台
    print("\n" + "="*50 + "\n")
    print(markdown_report)
    
    # 也可以选择写入文件，供前端或自动化流程读取
    # with open("market_news_report.md", "w", encoding="utf-8") as f:
    #     f.write(markdown_report)