<template>
  <v-container fluid>
    <div class="d-flex align-center mb-4">
      <h2 class="flex-grow-1">人设</h2>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openAdd">新建人设</v-btn>
    </div>
    <v-card>
      <v-list>
        <v-list-item v-for="p in personas" :key="p.id">
          <template #title>{{ p.name }}</template>
          <template #subtitle>{{ p.prompt }}</template>
          <template #append>
            <v-btn icon="mdi-pencil" variant="text" @click="openEdit(p)" />
            <v-btn icon="mdi-delete" variant="text" color="error" @click="del(p.id)" />
          </template>
        </v-list-item>
        <v-list-item v-if="!personas.length" title="（无人设，可新建；也可在群里说「设一个毒舌人设」）" />
      </v-list>
    </v-card>

    <v-dialog v-model="dialog" width="520">
      <v-card class="pa-4">
        <v-card-title>{{ editing ? '编辑人设' : '新建人设' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.name" label="名字" density="comfortable" />
          <v-textarea v-model="form.prompt" label="人设描述（如：毒舌幽默，说话简短犀利，爱用网络梗）" rows="4" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="dialog = false">取消</v-btn>
          <v-btn color="primary" @click="save">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" :timeout="2000">{{ snackText }}</v-snackbar>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const personas = ref([])
const dialog = ref(false)
const editing = ref(false)
const form = ref({ id: '', name: '', prompt: '' })
const snackbar = ref(false)
const snackText = ref('')

function showSnack(text) {
  snackText.value = text
  snackbar.value = true
}

async function load() {
  const { data } = await api.get('/personas')
  personas.value = data.personas
}
function openAdd() {
  editing.value = false
  form.value = { id: '', name: '', prompt: '' }
  dialog.value = true
}
function openEdit(p) {
  editing.value = true
  form.value = { id: p.id, name: p.name, prompt: p.prompt }
  dialog.value = true
}
async function save() {
  if (editing.value) {
    await api.put('/personas/' + form.value.id, form.value)
    showSnack('已更新')
  } else {
    await api.post('/personas', form.value)
    showSnack('已创建')
  }
  dialog.value = false
  await load()
}
async function del(id) {
  await api.delete('/personas/' + id)
  showSnack('已删除')
  await load()
}
onMounted(load)
</script>
