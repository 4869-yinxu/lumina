<template>
  <v-container fluid>
    <div class="d-flex align-center mb-4">
      <h2 class="flex-grow-1">模型供应商</h2>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openAdd">添加</v-btn>
    </div>
    <v-card>
      <v-list>
        <v-list-item v-for="p in providers" :key="p.id">
          <template #title>
            {{ p.id }}
            <v-chip v-if="p.id === defaultProvider" size="small" color="primary" class="ml-1">默认</v-chip>
            <v-chip size="small" class="ml-1">{{ typeZh(p.type) }}</v-chip>
          </template>
          <template #subtitle>{{ p.model }} · {{ p.base_url }}</template>
          <template #append>
            <v-btn icon="mdi-pencil" variant="text" @click="openEdit(p)" />
            <v-btn icon="mdi-delete" variant="text" color="error" @click="del(p.id)" />
          </template>
        </v-list-item>
        <v-list-item v-if="!providers.length" title="（无供应商）" />
      </v-list>
    </v-card>

    <v-dialog v-model="dialog" width="520">
      <v-card class="pa-4">
        <v-card-title>{{ editing ? '编辑供应商' : '添加供应商' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.id" label="id" density="comfortable" :disabled="editing" />
          <v-select v-model="form.type" :items="types" label="类型" density="comfortable" />
          <v-text-field v-model="form.base_url" label="base_url" density="comfortable" />
          <v-text-field v-model="form.api_key" label="api_key" density="comfortable" />
          <v-text-field v-model="form.model" label="model" density="comfortable" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="dialog = false">取消</v-btn>
          <v-btn color="primary" @click="save">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const providers = ref([])
const defaultProvider = ref('')
const dialog = ref(false)
const editing = ref(false)
const types = [
  { title: '对话', value: 'chat' },
  { title: '嵌入', value: 'embedding' },
  { title: '视觉', value: 'vision' },
  { title: '多模态', value: 'multimodal' },
]
const form = ref({ id: '', base_url: '', api_key: '', model: '', type: 'chat' })

function typeZh(t) {
  return { chat: '对话', embedding: '嵌入', vision: '视觉', multimodal: '多模态' }[t] || t
}

async function load() {
  const { data } = await api.get('/providers')
  providers.value = data.providers
  defaultProvider.value = data.default
}
function openAdd() {
  editing.value = false
  form.value = { id: '', base_url: '', api_key: '', model: '', type: 'chat' }
  dialog.value = true
}
function openEdit(p) {
  editing.value = true
  form.value = { id: p.id, base_url: p.base_url, api_key: '', model: p.model, type: p.type }
  dialog.value = true
}
async function save() {
  if (editing.value) {
    await api.put('/providers/' + form.value.id, form.value)
  } else {
    await api.post('/providers', form.value)
  }
  dialog.value = false
  await load()
}
async function del(id) {
  await api.delete('/providers/' + id)
  await load()
}
onMounted(load)
</script>
