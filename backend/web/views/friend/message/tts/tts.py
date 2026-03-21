import asyncio
import base64
import json
import os
import threading
import uuid
from queue import Queue

import websockets
from django.http import StreamingHttpResponse
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.friend import Friend


class SSERenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'txt'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class TextToSpeechView(APIView):
    """将指定文字通过角色音色合成为语音，以 SSE 流式返回 Base64 编码的 mp3 音频块。"""
    permission_classes = [IsAuthenticated]
    renderer_classes = [SSERenderer]

    def post(self, request):
        friend_id = request.data.get('friend_id')
        text = request.data.get('text', '').strip()

        if not text:
            return Response({'result': '文字不能为空'})

        friends = Friend.objects.filter(pk=friend_id, me__user=request.user)
        if not friends.exists():
            return Response({'result': '好友不存在'})

        friend = friends.first()
        voice_id = friend.character.voice.voice_id

        response = StreamingHttpResponse(
            self.event_stream(text, voice_id),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    async def tts_sender(self, text, ws, task_id):
        await ws.send(json.dumps({
            "header": {
                "action": "continue-task",
                "task_id": task_id,
                "streaming": "duplex"
            },
            "payload": {
                "input": {
                    "text": text,
                }
            }
        }))
        await ws.send(json.dumps({
            "header": {
                "action": "finish-task",
                "task_id": task_id,
                "streaming": "duplex"
            },
            "payload": {
                "input": {}
            }
        }))

    async def tts_receiver(self, mq, ws):
        async for msg in ws:
            if isinstance(msg, bytes):
                audio = base64.b64encode(msg).decode('utf-8')
                mq.put_nowait({'audio': audio})
            else:
                data = json.loads(msg)
                event = data['header']['event']
                if event in ['task-finished', 'task-failed']:
                    break

    async def run_tts_tasks(self, text, mq, voice_id):
        task_id = uuid.uuid4().hex
        api_key = os.getenv('API_KEY_EMB')
        wss_url = os.getenv('WSS_URL')
        headers = {"Authorization": f"Bearer {api_key}"}

        async with websockets.connect(wss_url, additional_headers=headers) as ws:
            await ws.send(json.dumps({
                "header": {
                    "action": "run-task",
                    "task_id": task_id,
                    "streaming": "duplex"
                },
                "payload": {
                    "task_group": "audio",
                    "task": "tts",
                    "function": "SpeechSynthesizer",
                    "model": "cosyvoice-v3-flash",
                    "parameters": {
                        "text_type": "PlainText",
                        "voice": voice_id,
                        "format": "mp3",
                        "sample_rate": 22050,
                        "volume": 50,
                        "rate": 1.10,
                        "pitch": 1
                    },
                    "input": {}
                }
            }))
            async for msg in ws:
                if json.loads(msg)['header']['event'] == 'task-started':
                    break
            await asyncio.gather(
                self.tts_sender(text, ws, task_id),
                self.tts_receiver(mq, ws),
            )

    def work(self, text, mq, voice_id):
        try:
            asyncio.run(self.run_tts_tasks(text, mq, voice_id))
        finally:
            mq.put_nowait(None)

    def event_stream(self, text, voice_id):
        mq = Queue()
        thread = threading.Thread(target=self.work, args=(text, mq, voice_id))
        thread.start()

        while True:
            msg = mq.get()
            if msg is None:
                break
            if msg.get('audio'):
                yield f'data: {json.dumps({"audio": msg["audio"]}, ensure_ascii=False)}\n\n'

        yield 'data: [DONE]\n\n'

