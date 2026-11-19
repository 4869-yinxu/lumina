<template>
  <v-container fluid>
    <h2 class="mb-4">权限管理</h2>
    <v-card class="mb-4 pa-4">
      <h4>授权</h4>
      <div class="d-flex gap-2 align-center">
        <v-text-field v-model="form.user_id" label="QQ 号" density="compact" class="mr-2" />
        <v-select v-model="form.level" :items="['developer', 'svip', 'vip']" label="级别" density="compact" class="mr-2" style="max-width:160px" />
        <v-btn color="primary" @click="grant">授予</v-btn>
      </div>
    </v-card>
    <v-row>
      <v-col v-for="lv in ['developer', 'svip', 'vip']" :key="lv" cols="12" md="4">
        <v-card>
          <v-card-title>{{ levelZh(lv) }}</v-card-title>
          <v-card-text>
            <v-chip v-for="u in (perms[lv] || [])" :key="u" class="ma-1">{{ u }}</v-chip>
            <div v-if="!(perms[lv] || []).length" class="text-medium-emphasis">（空）</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const perms = ref({})
const form = ref({ user_id: '', level: 'vip' })

function levelZh(lv) {
  return { developer: '开发者（全权）', svip: 'SVIP（协同开发）', vip: 'VIP（增强）' }[lv] || lv
}
async function load() {
  perms.value = (await api.get('/permissions')).data.permissions
}
async function grant() {
  await api.post('/permissions', { user_id: form.value.user_id, level: form.value.level })
  form.value.user_id = ''
  await load()
}
onMounted(load)
</script>
