import { fetchEventSource } from '@microsoft/fetch-event-source';
import api from "./api.js";
import {useUserStore} from "../../stores/user.js";
import CONFIG_API from "../config/config.js";

const BASE_URL = CONFIG_API.HTTP_URL

/**
 * 视觉推理流式请求
 * @param {string} friendId 好友 ID
 * @param {string} imageBase64 Base64 编码的图像
 * @param {string} textPrompt 文本提示词
 * @param {function} onmessage 消息回调
 * @param {function} onerror 错误回调
 */
export default async function visionApi(friendId, imageBase64, textPrompt, enableWebSearch, onmessage, onerror) {
    const userStore = useUserStore();


    const startFetch = async () => {
        return await fetchEventSource(BASE_URL + '/api/friend/message/vision/stream/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${userStore.accessToken}`,
            },
            body: JSON.stringify({
                friend_id: friendId,
                image: imageBase64,
                text: textPrompt,
                enable_web_search: enableWebSearch,
            }),

            openWhenHidden: true,
            async onopen(response) {
                if (response.status === 401) {
                    try {
                        await api.post('/api/user/account/refresh_token/', {});
                        throw new Error("TOKEN_REFRESHED");
                    } catch (err) {
                        throw err;
                    }
                }

                if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream')) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || `请求失败: ${response.status}`);
                }
            },

            onmessage(msg) {
                if (msg.data === '[DONE]') {
                    if (onmessage) onmessage('', true);
                    return
                }
                try {
                    const json = JSON.parse(msg.data);
                    if (onmessage) onmessage(json, false);
                } catch (e) {
                }
            },

            onerror(err) {
                if (err.message === "TOKEN_REFRESHED") {
                    return startFetch();
                }

                if (onerror) {
                    onerror(err);
                }
                throw err;
            },
        });
    };

    return await startFetch();
}

