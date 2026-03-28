import threading

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# user_id -> threading.Event
_cancel_events: dict[int, threading.Event] = {}
_lock = threading.Lock()


def register_cancel_event(user_id: int) -> threading.Event:
    event = threading.Event()
    with _lock:
        _cancel_events[user_id] = event
    return event


def clear_cancel_event(user_id: int) -> None:
    with _lock:
        _cancel_events.pop(user_id, None)


def is_cancelled(user_id: int) -> bool:
    with _lock:
        ev = _cancel_events.get(user_id)
    return ev is not None and ev.is_set()


class CancelSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.id
        with _lock:
            ev = _cancel_events.get(user_id)
        if ev:
            ev.set()
        return Response({'result': 'ok'})

