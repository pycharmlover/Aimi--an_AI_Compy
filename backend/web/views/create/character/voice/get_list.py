from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.character import Voice


class GetVoiceList(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            # 获取公开音色 + 当前用户的私有音色
            public_voices = Voice.objects.filter(is_public=True).order_by('id')
            user_voices = Voice.objects.filter(author__user=request.user, is_public=False).order_by('id')
            voices_raw = list(public_voices) + list(user_voices)
            
            voices = []
            for v in voices_raw:
                voices.append({
                    'id': v.id,
                    'name': v.name,
                })
            return Response({
                'result': 'success',
                'voices': voices,
            })
        except:
            return Response({
                'result': '系统异常，请稍后重试'
            })