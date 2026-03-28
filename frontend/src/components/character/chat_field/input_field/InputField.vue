<script setup>

import SendIcon from "../../icons/SendIcon.vue";
import MicIcon from "../../icons/MicIcon.vue";
import CameraIcon from "../../icons/CameraIcon.vue";
import {onUnmounted, ref, useTemplateRef} from "vue";
import streamApi from "../../../../js/http/streamApi.js";
import visionApi from "../../../../js/http/visionApi.js";
import Microphone from "./Microphone.vue";

const props = defineProps(['friendId'])
const emit = defineEmits(['pushBackMessage', 'addToLastMessage'])
const inputRef = useTemplateRef('input-ref')
const videoRef = useTemplateRef('video-ref')
const canvasRef = useTemplateRef('canvas-ref')
const message = ref('')
let processId = 0
const showMic = ref(false)
const enableWebSearch = ref(false)
const isWebSearching = ref(false)
const cameraActive = ref(false)
let stream = ref(null)
let frameInterval = ref(null)
let visionInProgress = false  // 防止并发推理
const cameraPosition = ref({ x: 20, y: 420 })  // 摄像头浮窗位置，默认在左下角输入栏上方
let isDragging = false
let dragOffset = { x: 0, y: 0 }

let mediaSource = null;
let sourceBuffer = null;
let audioPlayer = new Audio();
let audioQueue = [];
let isUpdating = false;

const initAudioStream = () => {
    audioPlayer.pause();
    audioQueue = [];
    isUpdating = false;

    mediaSource = new MediaSource();
    audioPlayer.src = URL.createObjectURL(mediaSource);

    mediaSource.addEventListener('sourceopen', () => {
        try {
            sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');
            sourceBuffer.addEventListener('updateend', () => {
                isUpdating = false;
                processQueue();
            });
        } catch (e) {
            // console.error("MSE AddSourceBuffer Error:", e);
        }
    });

    audioPlayer.play().catch(e => console.error("等待用户交互以播放音频"));
};

const processQueue = () => {
    if (isUpdating || audioQueue.length === 0 || !sourceBuffer || sourceBuffer.updating) {
        return;
    }

    isUpdating = true;
    const chunk = audioQueue.shift();
    try {
        sourceBuffer.appendBuffer(chunk);
    } catch (e) {
        // console.error("SourceBuffer Append Error:", e);
        isUpdating = false;
    }
};

const stopAudio = () => {
    audioPlayer.pause();
    audioQueue = [];
    isUpdating = false;

    if (mediaSource) {
        if (mediaSource.readyState === 'open') {
            try {
                mediaSource.endOfStream();
            } catch (e) {
            }
        }
        mediaSource = null;
    }

    if (audioPlayer.src) {
        URL.revokeObjectURL(audioPlayer.src);
        audioPlayer.src = '';
    }
};

const handleAudioChunk = (base64Data) => {
    try {
        const binaryString = atob(base64Data);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        audioQueue.push(bytes);
        processQueue();
    } catch (e) {
        // console.error("Base64 Decode Error:", e);
    }
};

onUnmounted(() => {
    audioPlayer.pause();
    audioPlayer.src = '';
    stopCamera();
});

function focus() {
  inputRef.value.focus()
}

async function startCamera() {
  try {
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    })
    
    // 先设置 cameraActive 为 true，让 video 元素挂载
    cameraActive.value = true

    // 等待 video 元素挂载
    await new Promise(resolve => setTimeout(resolve, 200))
    
    if (videoRef.value) {
      videoRef.value.srcObject = stream.value

      // 不再自动抽帧，改为手动触发
    } else {
      // console.error("[DEBUG] startCamera: videoRef 仍为 null");
    }
  } catch (err) {
    cameraActive.value = false
  }
}

function stopCamera() {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }
  if (frameInterval.value) {
    clearInterval(frameInterval.value)
    frameInterval.value = null
  }
  cameraActive.value = false
}

function captureFrame() {
  if (!videoRef.value || !canvasRef.value) return
  if (!message.value.trim()) {
    // console.log("[DEBUG] captureFrame: 提示词为空，跳过");
    return
  }

  // console.log("[DEBUG] captureFrame: 开始抽帧");
  const ctx = canvasRef.value.getContext('2d')
  canvasRef.value.width = videoRef.value.videoWidth
  canvasRef.value.height = videoRef.value.videoHeight
  ctx.drawImage(videoRef.value, 0, 0)

  const imageBase64 = canvasRef.value.toDataURL('image/jpeg', 0.8).split(',')[1]
  handleVisionFrame(imageBase64)
}

async function handleVisionFrame(imageBase64, prompt) {
  if (!prompt || !prompt.trim()) {
    // console.log("[DEBUG] 提示词为空，跳过推理");
    return
  }

  // 防止并发推理
  if (visionInProgress) {
    // console.log("[DEBUG] 推理进行中，跳过本次请求");
    return
  }

  visionInProgress = true

  try {
    await visionApi(
      props.friendId,
      imageBase64,
      prompt,
      (data, isDone) => {
        // console.log(`[DEBUG] 视觉推理回调 - isDone: ${isDone}, data: ${JSON.stringify(data).substring(0, 100)}`);
        if (data.content) {
          // console.log(`[DEBUG] 添加推理结果到聊天: ${data.content.substring(0, 50)}`);
          emit('addToLastMessage', data.content)
        }
        
        // 推理完成，重置标志
        if (isDone) {
          visionInProgress = false
        }
      },
      (err) => {
        visionInProgress = false
      }
    )
  } catch (err) {
    visionInProgress = false
  }
}

function toggleCamera() {
  if (cameraActive.value) {
    stopCamera()
  } else {
    startCamera()
  }
}

function handleCameraMouseDown(e) {
  isDragging = true
  dragOffset.x = e.clientX - cameraPosition.value.x
  dragOffset.y = e.clientY - cameraPosition.value.y
}

function handleMouseMove(e) {
  if (!isDragging) return
  cameraPosition.value.x = e.clientX - dragOffset.x
  cameraPosition.value.y = e.clientY - dragOffset.y
}

function handleMouseUp() {
  isDragging = false
}

async function handleSend(event, audio_msg) {
  let content
  if (audio_msg) {
    content = audio_msg.trim()
  } else {
    content = message.value.trim()
  }
  if (!content) return

  // 初始化音频流（文本和摄像头模式都需要）
  initAudioStream()

  const curId = ++ processId
  message.value = ''

  emit('pushBackMessage', {role: 'user', content: content, id: crypto.randomUUID()})
  emit('pushBackMessage', {role: 'ai', content: '', id: crypto.randomUUID()})

  // 如果摄像头打开，使用视觉推理；否则使用文本对话
  if (cameraActive.value) {
    // 手动抽帧并推理
    if (videoRef.value && canvasRef.value) {
      const ctx = canvasRef.value.getContext('2d')
      canvasRef.value.width = videoRef.value.videoWidth
      canvasRef.value.height = videoRef.value.videoHeight
      ctx.drawImage(videoRef.value, 0, 0)
      const imageBase64 = canvasRef.value.toDataURL('image/jpeg', 0.8).split(',')[1]
      
      // 触发视觉推理
      try {
        await visionApi(
          props.friendId,
          imageBase64,
          content,
          (data, isDone) => {
            if (curId !== processId) return
            
            if (data.content) {
              emit('addToLastMessage', data.content)
            }
            if (data.audio) {
              handleAudioChunk(data.audio)
            }
          },
          (err) => {
            // console.error(`[DEBUG] 视觉推理失败: ${err.message}`);
          }
        )
      } catch (err) {
        // console.error(`[DEBUG] 视觉推理错误: ${err.message}`);
      }
    }
    return
  }

  try {
    if (enableWebSearch.value) {
      isWebSearching.value = true
    }
    await streamApi('/api/friend/message/chat/', {
      body: {
        friend_id: props.friendId,
        message: content,
        enable_web_search: enableWebSearch.value,
      },
      onmessage(data, isDone) {
        if (curId !== processId) return

        if (data.content) {
          isWebSearching.value = false
          emit('addToLastMessage', data.content)
        }
        if (data.audio) {
          handleAudioChunk(data.audio)
        }
      },
      onerror(err) {
        isWebSearching.value = false
      },
    })
  } catch (err) {
    isWebSearching.value = false
  }
}

function close() {
  ++ processId
  showMic.value = false
  stopCamera()
  stopAudio()
}

function handleStop() {
  ++ processId
  stopAudio()
}

defineExpose({
  focus,
  close,
})
</script>

<template>
  <div v-if="!showMic" class="absolute bottom-4 left-2 w-86 flex flex-col gap-2" @mousemove="handleMouseMove" @mouseup="handleMouseUp" @mouseleave="handleMouseUp">
    <!-- 摄像头浮窗 - 显示在聊天框外 -->
    <div 
      v-if="cameraActive" 
      class="fixed bg-black rounded-lg overflow-hidden shadow-2xl cursor-move"
      :style="{
        left: cameraPosition.x + 'px',
        top: cameraPosition.y + 'px',
        width: '116px',
        zIndex: 0x3f3f3f3f
      }"
      @mousedown="handleCameraMouseDown"
    >
      <video
        ref="video-ref"
        autoplay
        playsinline
        class="w-full h-auto"
      />
      <canvas ref="canvas-ref" class="hidden" />
      <div class="absolute top-2 right-2 text-white text-xs bg-black/50 px-2 py-1 rounded pointer-events-none">
        拖动移动
      </div>
    </div>

    <!-- 联网搜索中提示 -->
    <div v-if="isWebSearching" class="flex items-center gap-2 px-3 py-1.5 text-white/70 text-sm">
      <div class="spinner-sm" aria-label="搜索中">
        <span v-for="n in 12" :key="n" class="spinner-sm-line"
          :style="{ transform: `rotate(${(n - 1) * 30}deg) translateY(-10px)` }"
        />
      </div>
      正在搜索网页，请稍后...
    </div>

    <!-- 输入框 -->
    <form @submit.prevent="handleSend" class="h-12 flex items-center">
      <input
          ref="input-ref"
          v-model="message"
          class="input bg-black/30 backdrop-blur-sm text-white text-base w-full h-full rounded-2xl pr-28"
          type="text"
          placeholder="文本输入..."
      >
      <div @click="handleSend" class="absolute right-2 w-8 h-8 flex justify-center items-center cursor-pointer">
        <SendIcon />
      </div>
      <div @click="showMic = true" class="absolute right-10 w-8 h-8 flex justify-center items-center cursor-pointer">
        <MicIcon />
      </div>
      <div
        @click="enableWebSearch = !enableWebSearch"
        :class="[
          'absolute right-26 w-8 h-8 flex justify-center items-center cursor-pointer rounded-full transition-colors',
          enableWebSearch ? 'text-emerald-300' : 'text-white/40'
        ]"
        title="联网搜索"
      >
        <!-- 小地球 SVG -->
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="none">
          <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.8"/>
          <path d="M12 4C9.8 6.2 8.5 9 8.5 12C8.5 15 9.8 17.8 12 20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          <path d="M12 4C14.2 6.2 15.5 9 15.5 12C15.5 15 14.2 17.8 12 20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          <path d="M4 12H20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </div>
      <div @click="toggleCamera" class="absolute right-18 w-8 h-8 flex justify-center items-center cursor-pointer">
        <CameraIcon />
      </div>
    </form>
  </div>

  <Microphone
      v-else
      @close="showMic = false"
      @send="handleSend"
      @stop="handleStop"
  />
</template>

<style scoped>
.spinner-sm {
  position: relative;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.spinner-sm-line {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 2.5px;
  height: 7px;
  margin-left: -1.25px;
  margin-top: -3.5px;
  border-radius: 999px;
  background: currentColor;
  transform-origin: center 10px;
  animation: spinner-fade 1.2s linear infinite;
}

.spinner-sm-line:nth-child(1)  { animation-delay: -1.1s; }
.spinner-sm-line:nth-child(2)  { animation-delay: -1.0s; }
.spinner-sm-line:nth-child(3)  { animation-delay: -0.9s; }
.spinner-sm-line:nth-child(4)  { animation-delay: -0.8s; }
.spinner-sm-line:nth-child(5)  { animation-delay: -0.7s; }
.spinner-sm-line:nth-child(6)  { animation-delay: -0.6s; }
.spinner-sm-line:nth-child(7)  { animation-delay: -0.5s; }
.spinner-sm-line:nth-child(8)  { animation-delay: -0.4s; }
.spinner-sm-line:nth-child(9)  { animation-delay: -0.3s; }
.spinner-sm-line:nth-child(10) { animation-delay: -0.2s; }
.spinner-sm-line:nth-child(11) { animation-delay: -0.1s; }
.spinner-sm-line:nth-child(12) { animation-delay:    0s; }

@keyframes spinner-fade {
  0%   { opacity: 1; }
  100% { opacity: 0.15; }
}
</style>
