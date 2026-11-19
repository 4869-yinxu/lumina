<template>
  <v-container fluid>
    <h2 class="mb-4">运行日志</h2>
    <v-card>
      <v-card-text class="text-caption" style="white-space: pre-wrap; font-family: monospace">
        {{ logs }}
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const logs = ref('')
async function load() {
  const { data } = await api.get('/logs')
  logs.value = data.logs.slice(-150).join('\n')
}
onMounted(load)
</script>
