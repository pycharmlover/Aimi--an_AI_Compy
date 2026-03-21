import os
import uuid
import time

from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.character import Voice
from web.views.create.character.voice.custom.create_voice import create_voice


class CreateCustomVoiceView(APIView):
    """接收前端上传的 mp3 音频 -> 保存到服务器 -> 获取外网 URL -> 调用复刻 API -> 存入数据库"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        audio_file = request.FILES.get('audio')
        voice_name = request.data.get('voice_name', '').strip()

        if not audio_file:
            return Response({'result': '音频文件不能为空'})
        if not voice_name:
            return Response({'result': '音色名称不能为空'})

        try:
            # 1. 保存音频文件到服务器
            ext = audio_file.name.split('.')[-1]
            filename = f'voice_custom/{request.user.id}_{uuid.uuid4().hex[:10]}.{ext}'
            
            from django.core.files.storage import default_storage
            file_path = default_storage.save(filename, ContentFile(audio_file.read()))
            
            # 等待文件完全写入
            time.sleep(0.5)
            
            # 2. 获取外网 URL
            voice_url = f'https://app7799.acapp.acwing.com.cn/media/{file_path}'

            # 3. 调用复刻 API
            result = create_voice(voice_url, voice_name)
            
            # 检查是否有 output 字段（成功响应）
            if 'output' not in result or 'voice_id' not in result['output']:
                error_msg = result.get('message') or result.get('error') or str(result)
                return Response({'result': f'语音复刻失败：{error_msg}'})

            voice_id = result['output']['voice_id']

            # 4. 存入数据库
            voice = Voice.objects.create(
                author_id=request.user.userprofile.id,
                name=voice_name,
                voice_id=voice_id,
                is_public=False,
            )

            return Response({
                'result': 'success',
                'voice': {
                    'id': voice.id,
                    'name': voice.name,
                }
            })

        except Exception as e:
            return Response({'result': f'系统异常：{str(e)}'})

