import logging

from .browser_executor import run_browser_search

logger = logging.getLogger(__name__)


def build_web_context_for_query(query: str) -> str:
    if not query:
        return ''

    try:
        final_text = run_browser_search(query)
        print("\n===== 填表结果 =====")
        print(final_text)
        print("===================\n")
    except Exception:
        logger.exception('Web search failed, falling back to empty context')
        return ''

    if not final_text:
        return ''

    return f'【联网检索信息】\n{final_text}\n'
