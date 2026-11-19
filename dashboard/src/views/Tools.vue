<template>
  <v-container fluid>
    <h2 class="mb-4">工具</h2>
    <v-expansion-panels multiple>
      <v-expansion-panel v-for="(items, cat) in categories" :key="cat">
        <v-expansion-panel-title>{{ cat }}（{{ items.length }}）</v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item v-for="t in items" :key="t.name">
              <template #title>
                <span>{{ t.description }}</span>
                <span class="text-caption ml-2" :class="riskClass(t.risk)">{{ riskZh(t.risk) }}</span>
              </template>
              <template #subtitle><code class="text-caption">{{ t.name }}</code></template>
              <template #append>
                <v-switch
                  v-if="t.risk === 'risky'"
                  :model-value="t.enabled"
                  density="compact"
                  hide-details
                  inset
                  @update:model-value="(v) => toggle(t.name, v)"
                />
              </template>
            </v-list-item>
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const categories = ref({})

function riskClass(risk) {
  return { safe: 'text-green', risky: 'text-orange', forbidden: 'text-red' }[risk] || ''
}
function riskZh(risk) {
  return { safe: '安全', risky: '需开启', forbidden: '禁用' }[risk] || risk
}

async function load() {
  const { data } = await api.get('/tools')
  categories.value = data.categories
}
async function toggle(name, on) {
  const { data } = await api.get('/status')
  const cur = new Set(data.allow_risky)
  if (on) cur.add(name)
  else cur.delete(name)
  await api.post('/allowlist', { allow: [...cur] })
  await load()
}
onMounted(load)
</script>
