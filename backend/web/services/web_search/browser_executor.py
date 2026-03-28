import asyncio
import os
os.environ.setdefault("BROWSER_USE_LOGGING_LEVEL", "warning")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

from browser_use import Agent, Browser, ChatOpenAI

_browser = Browser()


def _build_llm():
    api_key = os.getenv('API_KEY')
    base_url = os.getenv('API_BASE')
    model = os.getenv('MODEL')

    if not api_key:
        raise ValueError('缺少 API_KEY')
    if not base_url:
        raise ValueError('缺少 API_BASE')
    if not model:
        raise ValueError('缺少 MODEL')

    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=0.1,
    )


def _build_search_answer_task(query: str) -> str:
    return f"""
你是一个网页研究助手。你的任务是基于网页搜索回答用户问题。

用户问题：
{query}

要求：
1. 打开 Baidu（https://www.baidu.com）。
2. 搜索该问题，点击最相关的结果。
3. 阅读页面内容，提取关键事实。
4. 必须以"最终答案："开头，给出精炼的人类可读答案。

输出格式：
最终答案：
<中文简述>

关键点：
- <要点>

来源：
- <标题> | <URL>
""".strip()


async def _run_browser_search_async(query: str) -> str:
    llm = _build_llm()
    agent = Agent(
        task=_build_search_answer_task(query),
        llm=llm,
        browser=_browser,
        use_vision=os.getenv('USE_VISION', 'false').lower() == 'true',
        max_steps=int(os.getenv('MAX_STEPS', '30')),
    )
    result = await agent.run()
    return result.final_result() or ''


def run_browser_search(query: str) -> str:
    return asyncio.run(_run_browser_search_async(query))
