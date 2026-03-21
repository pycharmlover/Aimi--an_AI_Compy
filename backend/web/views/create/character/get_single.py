from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.character import Character, Voice


class GetSingleCharacterView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self,request):
        try:
            character = request.query_params.get('character_id')
            character = Character.objects.get(pk=character, author__user=request.user)

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
                'character': {
                    'id': character.id,
                    'name': character.name,
                    'profile': character.profile,
                    'photo': character.photo.url,
                    'background_image': character.background_image.url,
                    'voice_id': character.voice.id,
                },
                'voices': voices,
            })
        except:
            return Response({
                'result': '系统异常，请稍后重试'
            })