<script setup>
import {ref, useTemplateRef} from "vue"
import api from "@/js/http/api.js"
import UploadIcon from "./icons/UploadIcon.vue"

const props = defineProps(['onVoiceCreated'])

const fileInputRef = useTemplateRef('file-input-ref')
const isUploading = ref(false)
const voiceName = ref('')
const errorMessage = ref('')

async function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (!file) return

  voiceName.value = file.name.replace(/\.[^/.]+$/, '')
}

async function handleUpload() {
  if (!voiceName.value.trim()) {
    errorMessage.value = '请输入音色名称'
    return
  }

  if (!fileInputRef.value?.files?.[0]) {
    errorMessage.value = '请选择音频文件'
    return
  }

  isUploading.value = true
  errorMessage.value = ''

  try {
    const formData = new FormData()
    formData.append('audio', fileInputRef.value.files[0])
    formData.append('voice_name', voiceName.value.trim())

    const res = await api.post('/api/create/character/voice/custom/create/', formData)
    const data = res.data

    if (data.result === 'success') {
      props.onVoiceCreated(data.voice)
      voiceName.value = ''
      fileInputRef.value.value = ''
    } else {
      errorMessage.value = data.result
    }
  } catch (err) {
    errorMessage.value = '上传失败，请重试'
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center gap-2">
      <input
        ref="file-input-ref"
        type="file"
        accept="audio/mp3,audio/*"
        @change="handleFileSelect"
        class="file-input file-input-bordered file-input-sm w-full"
        :disabled="isUploading"
      />
      <button
        @click="handleUpload"
        :disabled="isUploading"
        class="btn btn-sm btn-primary gap-1"
      >
        <UploadIcon />
        {{ isUploading ? '上传中...' : '上传' }}
      </button>
    </div>
    <input
      v-model="voiceName"
      type="text"
      placeholder="输入音色名称"
      class="input input-bordered input-sm"
      :disabled="isUploading"
    />
    <p v-if="errorMessage" class="text-xs text-red-500">{{ errorMessage }}</p>
  </div>
</template>

<style scoped>
</style>

