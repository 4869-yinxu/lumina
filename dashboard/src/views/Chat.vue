<template>
  <v-container fluid>
    <h2 class="mb-4">聊天测试</h2>
    <v-card class="mb-4" variant="outlined">
      <v-card-text ref="box" class="overflow-y-auto" style="height: 420px">
        <div v-for="(m, i) in messages" :key="i" class="mb-2">
          <div :class="m.role === 'user' ? 'text-primary' : ''">
            <b>{{ m.role === 'user' ? '我' : 'bot' }}</b> {{ m.text }}
          </div>
        </div>
      </v-card-text>
    </v-card>
    <div class="d-flex gap-2">
      <v-text-field v-model="input" label="消息" hide-details @keyup.enter="send" />
      <v-btn color="primary" class="ml-2" @click="send">发送</v-btn>
    </div>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const messages = ref([])
const input = ref('')
const box = ref(null)

async function send() {
  const text = input.value.trim()
  if (!text) return
  input.value = ''
  messages.value.push({ role: 'user', text })
  const { data } = await api.post('/chat', { message: text })
  messages.value.push({ role: 'bot', text: data.reply })
}
</script>
