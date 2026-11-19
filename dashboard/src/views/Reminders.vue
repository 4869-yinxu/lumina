<template>
  <v-container fluid>
    <h2 class="mb-4">定时任务</h2>
    <v-card>
      <v-list>
        <v-list-item v-for="r in reminders" :key="r.id">
          <template #title>{{ r.id }}</template>
          <template #subtitle>next {{ r.next_run }} · args={{ JSON.stringify(r.args) }}</template>
          <template #append>
            <v-btn icon="mdi-close" variant="text" color="error" @click="cancel(r.id)" />
          </template>
        </v-list-item>
        <v-list-item v-if="!reminders.length" title="（无定时任务）" />
      </v-list>
    </v-card>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const reminders = ref([])
async function load() {
  const { data } = await api.get('/reminders')
  reminders.value = data.reminders
}
async function cancel(id) {
  await api.post('/reminders/' + id + '/cancel')
  await load()
}
onMounted(load)
</script>
