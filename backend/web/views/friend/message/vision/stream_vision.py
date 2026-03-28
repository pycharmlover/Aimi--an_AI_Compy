import asyncio
import base64
import json
import os
import threading
import uuid
from io import BytesIO
from queue import Queue

import websockets
from django.http import StreamingHttpResponse
from langchain_core.messages import HumanMessage, BaseMessageChunk, SystemMessage
from langchain_openai import ChatOpenAI as LangChainOpenAI
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from PIL import Image

from web.models.friend import Friend
from web.services.web_search import build_web_context_for_query
from web.views.friend.message.cancel import register_cancel_event, clear_cancel_event, make_cancel_check
from web.views.friend.message.chat.chat import parse_bool
from web.views.friend.message.chat.graph import ChatGraph



def _build_search_query_from_image(image_base64: str, text_prompt: str) -> str:
    """用多模态模型分析图像 + 用户问题，生成适合搜索引擎的具体搜索词。"""
    llm = LangChainOpenAI(
        model='Qwen/Qwen3.5-122B-A10B',
        openai_api_key=os.getenv('API_KEY'),
        openai_api_base=os.getenv('API_BASE'),
        temperature=0.2,
    )
    message_content = [
        {
            'type': 'image_url',
            'image_url': {'url': f'data:image/jpeg;base64,{image_base64}'}
        },
        {
            'type': 'text',
            'text': (
                f'用户正在看这张图片，并提问："{text_prompt}"\n'
                '请根据图片内容和用户问题，生成一个简洁精准、适合在搜索引擎中搜索的中文关键词组合（不超过20个字），'
                '不要任何解释，只输出搜索词本身。'
            )
        }
    ]
    resp = llm.invoke([HumanMessage(content=message_content)])
    query = resp.content.strip()
    return query or text_prompt


class SSERenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'txt'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class StreamVisionView(APIView):
    """接收图像帧 + 文本提示，通过多模态模型流式推理，返回理解结果和音频"""
    permission_classes = [IsAuthenticated]
    renderer_classes = [SSERenderer]

    def post(self, request):
        friend_id = request.data.get('friend_id')
        image_base64 = request.data.get('image')
        text_prompt = request.data.get('text', '').strip()
        enable_web_search = parse_bool(request.data.get('enable_web_search', False))

        if not image_base64:
            return Response({'result': '图像不能为空'})
        if not text_prompt:
            return Response({'result': '提示词不能为空'})

        friends = Friend.objects.filter(pk=friend_id, me__user=request.user)
        if not friends.exists():
            return Response({'result': '好友不存在'})

        friend = friends.first()

        web_context = ''
        if enable_web_search:
            search_id = register_cancel_event(request.user.id)
            try:
                search_query = _build_search_query_from_image(image_base64, text_prompt)
                web_context = build_web_context_for_query(
                    search_query,
                    cancel_check=make_cancel_check(search_id),
                )
            finally:
                clear_cancel_event(request.user.id, search_id)

        app = ChatGraph.create_app()

        try:
            # 1. 解码 Base64 图像
            image_data = base64.b64decode(image_base64)
            image = Image.open(BytesIO(image_data))

            # 2. 构建多模态消息（图像 + 文本）
            message_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": text_prompt
                }
            ]

            msgs = [HumanMessage(content=message_content)]
            if web_context:
                msgs = [SystemMessage(web_context)] + msgs

            inputs = {
                'messages': msgs
            }

            response = StreamingHttpResponse(
                self.event_stream(app, inputs, friend),
                content_type='text/event-stream',
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'result': f'处理失败：{str(e)}'})

    async def tts_sender(self, app, inputs, mq, ws, task_id):
        async for msg, metadata in app.astream(inputs, stream_mode="messages"):
            if isinstance(msg, BaseMessageChunk):
                if msg.content:
                    await ws.send(json.dumps({
                        "header": {
                            "action": "continue-task",
                            "task_id": task_id,
                            "streaming": "duplex"
                        },
                        "payload": {
                            "input": {
                                "text": msg.content,
                            }
                        }
                    }))
                    mq.put_nowait({'content': msg.content})
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

    async def run_tts_tasks(self, app, inputs, mq, voice_id):
        task_id = uuid.uuid4().hex
        api_key = os.getenv('API_KEY_EMB')
        wss_url = os.getenv('WSS_URL')
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
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
                self.tts_sender(app, inputs, mq, ws, task_id),
                self.tts_receiver(mq, ws),
            )

    def work(self, app, inputs, mq, voice_id):
        try:
            asyncio.run(self.run_tts_tasks(app, inputs, mq, voice_id))
        finally:
            mq.put_nowait(None)

    def event_stream(self, app, inputs, friend):
        mq = Queue()
        thread = threading.Thread(target=self.work, args=(app, inputs, mq, friend.character.voice.voice_id))
        thread.start()

        full_output = ''
        while True:
            msg = mq.get()
            if not msg:
                break
            if msg.get('content', None):
                full_output += msg['content']
                yield f'data: {json.dumps({"content": msg["content"]}, ensure_ascii=False)}\n\n'
            if msg.get('audio', None):
                yield f'data: {json.dumps({"audio": msg["audio"]}, ensure_ascii=False)}\n\n'

        yield 'data: [DONE]\n\n'

