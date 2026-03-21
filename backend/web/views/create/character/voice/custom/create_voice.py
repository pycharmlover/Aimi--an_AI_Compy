import os
import requests


def create_voice(voice_url, prefix):
    """调用阿里云语音复刻 API"""
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
    
    try:
        response = requests.post(os.getenv('VOICE_URL'), headers=headers, json=data, timeout=30)
        result = response.json()
        return result
    except requests.exceptions.RequestException as e:
        return {"message": f"请求失败：{str(e)}"}

# if __name__ == '__main__':
#     vs = [] #填写media/voice_tmp中字符串名称
#     for v in vs:
#         print(create_voice(f'https://app7799.acapp.acwing.com.cn/media/voice_tmp/{v}.mp3', v))
#
