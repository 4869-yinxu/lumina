<template>
  <v-container fluid>
    <h2 class="mb-4">对话记录</h2>
    <div class="d-flex gap-2 align-center mb-4">
      <v-select v-model="scope" :items="scopes" label="选择会话" @update:model-value="loadMsgs" class="flex-grow-1" />
      <v-btn color="error" variant="tonal" prepend-icon="mdi-delete" :disabled="!scope" @click="clearScope">清空该会话</v-btn>
    </div>
    <v-card>
      <v-card-text class="text-body-2">
        <div v-for="(m, i) in messages" :key="i" class="mb-1">
          <b>{{ m.role }}</b> {{ m.content }}
        </div>
        <div v-if="!messages.length" class="text-medium-emphasis">选择会话查看内容</div>
      </v-card-text>
    </v-card>
    <v-snackbar v-model="snackbar" :timeout="2000">{{ snackText }}</v-snackbar>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const scopes = ref([])
const scope = ref('')
const messages = ref([])
const snackbar = ref(false)
const snackText = ref('')

async function loadScopes() {
  const { data } = await api.get('/conversations')
  scopes.value = data.scopes
}
async function loadMsgs() {
  if (!scope.value) return
  const { data } = await api.get('/conversations/' + encodeURIComponent(scope.value))
  messages.value = data.messages
}
async function clearScope() {
  if (!scope.value) return
  await api.delete('/conversations/' + encodeURIComponent(scope.value))
  snackText.value = '已清空'
  snackbar.value = true
  messages.value = []
  await loadScopes()
}
onMounted(loadScopes)
</script>
