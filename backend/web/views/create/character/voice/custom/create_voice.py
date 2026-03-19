import os

import requests


def create_voice(voice_url, prefix):
    # 阿里云定义好的
    headers = {
        "Authorization": f"Bearer {os.getenv('API_KEY_EMB')}",
        "Content-Type": "application/json"
    }

    data = {
       "model": "voice-enrollment",
       "input": {
           "action": "create_voice",
           "target_model": "cosyvoice-v3-flash",
           "prefix": prefix,
           "url": voice_url,
       }
    }
    response = requests.post(os.getenv('VOICE_URL'), headers=headers, json=data)
    return response.json()

# if __name__ == '__main__':
#     vs = [] #填写media/voice_tmp中字符串名称
#     for v in vs:
#         print(create_voice(f'https://app7799.acapp.acwing.com.cn/media/voice_tmp/{v}.mp3', v))
#
