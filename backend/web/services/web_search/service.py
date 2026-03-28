from .browser_executor import run_browser_search



def build_web_context_for_query(query: str, cancel_check=None) -> str:
    if not query:
        return ''

    if cancel_check and cancel_check():
        return ''

    try:
        final_text = run_browser_search(query, cancel_check=cancel_check)
    except Exception:
        return ''

    if cancel_check and cancel_check():
        return ''

    if not final_text:
        return ''

    return f'【联网检索信息】\n{final_text}\n'
