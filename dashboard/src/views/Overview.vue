<template>
  <v-container fluid>
    <h2 class="mb-4">概览</h2>
    <v-row>
      <v-col v-for="(s, i) in stats" :key="i" cols="6" md="2">
        <v-card>
          <v-card-text class="text-center">
            <div class="text-subtitle-2 text-medium-emphasis">{{ s.label }}</div>
            <div class="text-h5 mt-1">{{ s.value }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <v-card class="mt-4">
      <v-card-title>常驻工具（默认可用的能力）</v-card-title>
      <v-card-text class="text-body-2">{{ alwaysOn.join('、') }}</v-card-text>
    </v-card>
    <v-card class="mt-4">
      <v-card-title>已放开的风险动作</v-card-title>
      <v-card-text class="text-body-2">{{ allowRisky.length ? allowRisky.join(', ') : '（无）' }}</v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const status = ref(null)
const alwaysOn = computed(() => status.value?.always_on_zh || [])
const allowRisky = computed(() => status.value?.allow_risky || [])
const stats = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { label: 'bot QQ', value: s.bot_id },
    { label: '模型', value: s.model },
    { label: '供应商', value: s.provider },
    { label: '工具数', value: s.tools_total },
    { label: 'safe', value: s.tools_by_risk?.safe },
    { label: 'risky', value: s.tools_by_risk?.risky },
  ]
})

onMounted(async () => {
  status.value = (await api.get('/status')).data
})
</script>
