import os
import threading
import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

_KEY_PREFIX = 'cancel_search:'
_TTL = 300  # Redis key 自动过期秒数


def _key(search_id: str) -> str:
    return f'{_KEY_PREFIX}{search_id}'


# ---------------------------------------------------------------------------
# 后端存储：优先 Redis（生产多进程），回退内存 threading.Event（本地单进程）
# ---------------------------------------------------------------------------

def _make_redis():
    """尝试连接 Redis；失败则返回 None，自动降级为内存模式。"""
    try:
        import redis
        r = redis.Redis(
            host=os.getenv('REDIS_HOST', '127.0.0.1'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=1,
        )
        r.ping()
        return r
    except Exception:
        return None


_redis = _make_redis()
_USE_REDIS = _redis is not None

# 内存模式：search_id -> threading.Event
_cancel_events: dict[str, threading.Event] = {}
_lock = threading.Lock()

# user_id -> 当前 search_id（用于 cancel 接口找到正确的 event）
_user_search: dict[int, str] = {}


# ---------------------------------------------------------------------------
# 统一接口
# ---------------------------------------------------------------------------

def register_cancel_event(user_id: int) -> str:
    """
    搜索开始前调用。
    返回本次搜索的唯一 search_id，调用方需保存并传给 make_cancel_check。
    """
    search_id = uuid.uuid4().hex
    if _USE_REDIS:
        # 记录 user_id -> search_id 映射，供 cancel 接口查询
        _redis.set(f'user_search:{user_id}', search_id, ex=_TTL)
        # 初始状态：未取消（key 不存在）
        _redis.delete(_key(search_id))
    else:
        event = threading.Event()
        with _lock:
            _user_search[user_id] = search_id
            _cancel_events[search_id] = event
    return search_id


def clear_cancel_event(user_id: int, search_id: str) -> None:
    """搜索结束后调用：清除本次搜索的标志。"""
    if _USE_REDIS:
        _redis.delete(_key(search_id))
        _redis.delete(f'user_search:{user_id}')
    else:
        with _lock:
            _cancel_events.pop(search_id, None)
            if _user_search.get(user_id) == search_id:
                _user_search.pop(user_id, None)


def make_cancel_check(search_id: str):
    """返回一个 cancel_check 函数，绑定到本次搜索的 search_id。"""
    if _USE_REDIS:
        def _check():
            return _redis.exists(_key(search_id)) == 1
    else:
        def _check():
            with _lock:
                ev = _cancel_events.get(search_id)
            return ev is not None and ev.is_set()
    return _check


class CancelSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.id
        if _USE_REDIS:
            search_id = _redis.get(f'user_search:{user_id}')
            if search_id:
                _redis.set(_key(search_id), '1', ex=_TTL)
        else:
            with _lock:
                search_id = _user_search.get(user_id)
                ev = _cancel_events.get(search_id) if search_id else None
            if ev:
                ev.set()
        return Response({'result': 'ok'})
