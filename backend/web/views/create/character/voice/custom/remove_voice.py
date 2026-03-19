import os

import requests


def delete_voice(voice_id):
    headers = {
        "Authorization": f"Bearer {os.getenv('API_KEY_EMB')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "voice-enrollment",
        "input": {
            "action": "delete_voice",
            "voice_id": voice_id,
        }
    }
    response = requests.post(os.getenv('VOICE_URL'), headers=headers, json=data)
    return response.json()

# if __name__ == '__main__':
#     res = list_voice()
#     for v in res['output']['voice_list']:
#         print(delete_voice(v['voice_id']))