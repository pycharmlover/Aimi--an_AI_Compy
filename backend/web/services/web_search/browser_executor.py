import asyncio
import os

os.environ.setdefault("BROWSER_USE_LOGGING_LEVEL", "warning")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

from browser_use import Agent, Browser, ChatOpenAI
from langchain_openai import ChatOpenAI as LangChainOpenAI

def _build_browser_llm():
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


def _build_decompose_llm():
    api_key = os.getenv('API_KEY')
    base_url = os.getenv('API_BASE')

    if not api_key:
        raise ValueError('缺少 API_KEY')
    if not base_url:
        raise ValueError('缺少 API_BASE')

    return LangChainOpenAI(
        model='deepseek-ai/DeepSeek-V3',
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.0,
    )


def _decompose_query(query: str) -> list[str]:
    """调用小模型把用户 query 拆解为 1~N 个子查询，返回列表。"""
    llm = _build_decompose_llm()
    prompt = f"""将下面的用户问题拆解为若干个独立的、适合直接搜索引擎搜索的子查询。
规则：
- 每个子查询单独一行，不带编号或符号前缀，不做任何解释。
- 子查询数量不超过 3 个。
- 如果问题本身已经足够简单或只涉及单一事实，只输出原问题一行即可。
- 不要把同一个问题改写成多个近义版本，只有在问题真正涉及多个独立信息点时才拆解。

用户问题：{query}"""

    response = llm.invoke(prompt)
    raw = response.content.strip()
    subqueries = [line.strip() for line in raw.splitlines() if line.strip()]
    if not subqueries:
        subqueries = [query]
    return subqueries


def _build_search_answer_task(query: str) -> str:
    return f"""你是一个网页研究助手。请用最少的步骤完成以下搜索任务。

用户问题：
{query}

执行规则（严格遵守，不得多余操作）：
1. 打开 Baidu（https://www.baidu.com）并搜索该问题。
2. 如果搜索结果页面已直接显示答案，立即提取并调用 done 结束。不要再点击任何链接。
3. 仅当搜索结果页面没有直接答案时，才执行scroll / extract等操作寻找并点击最相关的一条结果。
4. 提取到答案后必须立刻调用 done，不得再执行任何 scroll / extract / click 操作。

输出格式（必须以"最终答案："开头）：
最终答案：
<中文简述>

关键点：
- <要点>

来源：
- <标题> | <URL>""".strip()


async def _run_browser_search_async(query: str, cancel_check=None) -> str:
    """每次搜索创建独立的 Browser 实例，避免复用导致的状态污染。"""
    browser = Browser()
    agent_task = None
    try:
        llm = _build_browser_llm()
        agent = Agent(
            task=_build_search_answer_task(query),
            llm=llm,
            browser=browser,
            use_vision=os.getenv('USE_VISION', 'false').lower() == 'true',
            max_steps=int(os.getenv('MAX_STEPS', '30')),
        )

        loop = asyncio.get_running_loop()
        agent_task = loop.create_task(agent.run())

        # 监控取消信号，每 0.5 秒检查一次
        async def _watch_cancel():
            while not agent_task.done():
                await asyncio.sleep(0.5)
                if cancel_check and cancel_check():
                    agent_task.cancel()
                    return

        if cancel_check:
            watcher = loop.create_task(_watch_cancel())
        else:
            watcher = None

        try:
            result = await agent_task
            return result.final_result() or ''
        except asyncio.CancelledError:
            return ''
        finally:
            if watcher and not watcher.done():
                watcher.cancel()
                try:
                    await watcher
                except asyncio.CancelledError:
                    pass
    finally:
        try:
            await browser.kill()
        except Exception:
            pass


async def _run_all_searches_async(subqueries: list[str], cancel_check=None) -> str:
    parts = []
    for i, q in enumerate(subqueries, 1):
        if cancel_check and cancel_check():
            break
        try:
            r = await _run_browser_search_async(q, cancel_check=cancel_check)
        except Exception as e:
            continue
        if cancel_check and cancel_check():
            break
        if r:
            if len(subqueries) > 1:
                parts.append(f'【子查询 {i}：{q}】\n{r}')
            else:
                parts.append(r)

    return '\n\n'.join(parts)


def run_browser_search(query: str, cancel_check=None) -> str:
    subqueries = _decompose_query(query)
    return asyncio.run(_run_all_searches_async(subqueries, cancel_check=cancel_check))
