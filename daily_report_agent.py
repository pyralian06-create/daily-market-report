import os
from typing import TypedDict, Annotated, List, Dict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode
from collect_tools import collect_information
from langchain_core.messages import SystemMessage
from datetime import datetime
from pydantic import BaseModel, Field
from operator import add

# 加载API key
load_dotenv()

class CollectResult(BaseModel):
    type: str = Field(description="数据源类型，如 'a_stock_overview'")
    result: str = Field(description="数据源采集结果")


# ========== 1. 定义状态 ==========
# messages字段用add_messages标注，LangGraph会自动把新消息append到列表里
class DailyReportState(TypedDict):
    messages: Annotated[list, add_messages] # llm有时需要做一些决策
    collect_result: Dict
    errors: Annotated[Dict[str, List[str]], add]
    retry_nums: Dict
    source_type: List



# ========== 2. 初始化Gemini ==========
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",  # Flash版免费额度大，够练手
    temperature=0.1,
)

tool_list = [collect_information]
llm_with_tools = llm.bind_tools(tool_list)

def get_system_prompt():
    return 
    """
        todo 补充日报分析模块的全局设定
    """

# ========== 3. 定义节点 ==========

# 1. 初始化
def init_node(state: DailyReportState) -> dict:
    """加载配置、清空 state"""
    from datetime import datetime
    return {
        "messages": [],
        "collect_result": {},
        "errors": {},
        "retry_nums": {},
        "source_type": []
    }
    return {}

def collect_information(state: DailyReportState) -> dict:
    """
    采集数据源：
    type有几种类型
    a_stock_overview 表示 A股今日的涨跌幅信息和宏观数据
    chinese_marco 表示 中国的宏观信息
    global_marco 表示 全球市场的某些重要指数的涨跌幅以及一些宏观信息
    rss_news 表示 采集的新闻信息
    """
    return {}

def write_report_node(state: DailyReportState) -> dict:
    state.get("collect_result").get("")
    return {}


MAX_RETRY_NUM = 3  # 每个数据源最多重试3次


# ========== 4. 构建图 ==========
workflow = StateGraph(AgentState)
workflow.add_node("chat", chat_node)
workflow.add_node("tool", tool_node)   # ← 新增：注册tool节点
workflow.add_edge(START, "chat")
workflow.add_conditional_edges(
    "chat",               # 从哪个节点出发
    should_use_tool,     # 路由函数，决定去哪
    {
        "use_tool": "tool",   # 返回"use_tool"就去tool_node
        "done": END,                # 返回"done"就结束
    }
)
workflow.add_edge("tool", "chat")

app = workflow.compile()

# ========== 5. 运行 ==========
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 简单Agent v0.1 - 回声机器人")
    print("输入 'quit' 退出")
    print("=" * 50)
    
    # 保留对话历史,实现多轮对话
    history = []
    turn_count = 0
    while True:
        user_input = input("\n你: ").strip()
        if user_input.lower() in ["quit", "exit", "q"]:
            print("👋 再见！")
            break
        if not user_input:
            continue
        
        # 把新消息加进历史
        history.append(HumanMessage(content=user_input))
        
        # 调用图
        result = app.invoke({"messages": history, "turn_count": turn_count})
        
        # 更新历史
        history = result["messages"]

        # 打印最后一条AI回复
        last_msg = result["messages"][-1]
        # 如果是 AIMessage，它的 .content 属性就是内容
        if hasattr(last_msg, "content"):
            content = last_msg.content
    
        # 情况 1: content 是纯字符串
        if isinstance(content, str):
            print(f"\n🤖 AI: {content}")
    
        # 情况 2: content 是列表 (Gemini 3 常见情况)
        elif isinstance(content, list):
            # 提取所有类型为 'text' 的部分并拼接
            full_text = "".join([part["text"] for part in content if isinstance(part, dict) and "text" in part])
            print(f"\n🤖 AI: {full_text}")
       