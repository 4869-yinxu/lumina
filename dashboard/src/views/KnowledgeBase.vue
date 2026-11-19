<template>
  <v-container fluid>
    <h2 class="mb-4">知识库</h2>
    <v-card class="pa-4 mb-4">
      <v-text-field v-model="ns" label="命名空间（如 user:123）" density="comfortable" class="mb-2" />
      <v-textarea v-model="text" label="内容" rows="2" class="mb-2" />
      <v-btn color="primary" prepend-icon="mdi-plus" @click="add">添加条目</v-btn>
    </v-card>
    <v-card>
      <v-list>
        <v-list-item v-for="d in docs" :key="d.id">
          <template #title>#{{ d.id }} · {{ d.namespace }}</template>
          <template #subtitle>{{ d.text }}</template>
          <template #append>
            <v-btn icon="mdi-delete" variant="text" color="error" @click="del(d.id)" />
          </template>
        </v-list-item>
        <v-list-item v-if="!docs.length" title="（无知识库条目）" />
      </v-list>
    </v-card>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const docs = ref([])
const ns = ref('')
const text = ref('')

async function load() {
  const { data } = await api.get('/kb')
  docs.value = data.docs
}
async function add() {
  await api.post('/kb', { text: text.value, namespace: ns.value || 'manual' })
  text.value = ''
  await load()
}
async function del(id) {
  await api.delete('/kb/' + id)
  await load()
}
onMounted(load)
</script>
