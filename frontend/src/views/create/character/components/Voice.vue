<script setup>
import {ref, watch} from "vue";
import UploadVoice from "./UploadVoice.vue"

const props = defineProps(['voices', 'curVoiceId'])

const myVoice = ref(props.curVoiceId)
const showUpload = ref(false)
const voiceList = ref([...props.voices])

watch(() => props.curVoiceId, newVal => {
  myVoice.value = newVal
})

watch(() => props.voices, newVal => {
  voiceList.value = [...newVal]
}, { deep: true })

function handleVoiceCreated(newVoice) {
  voiceList.value.push(newVoice)
  myVoice.value = newVoice.id
  showUpload.value = false
}

defineExpose({
  myVoice,
})
</script>

<template>
  <fieldset class="fieldset">
    <label class="label text-base">音色</label>
    <div class="flex gap-2 items-start">
      <select v-model="myVoice" @change="showUpload = myVoice === 'custom'" class="select flex-1">
        <option value="custom">自定义音色</option>
        <option
          v-for="voice in voiceList"
          :key="voice.id"
          :value="voice.id"
        >{{ voice.name }}</option>
      </select>
    </div>
    <div v-if="showUpload" class="mt-3">
      <UploadVoice :onVoiceCreated="handleVoiceCreated" />
    </div>
  </fieldset>
</template>

<style scoped>

</style>