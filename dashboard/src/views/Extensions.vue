<template>
  <v-container fluid>
    <h2 class="mb-4">扩展</h2>
    <v-tabs v-model="tab">
      <v-tab value="mcp">MCP</v-tab>
      <v-tab value="skills">Skills</v-tab>
      <v-tab value="plugins">插件</v-tab>
    </v-tabs>

    <v-tabs-window v-model="tab">
      <!-- MCP -->
      <v-tabs-window-item value="mcp">
        <v-card class="mt-4 pa-4">
          <v-list density="compact">
            <v-list-item v-for="s in mcpServers" :key="s.name">
              <template #title>
                {{ s.name }}
                <v-chip v-if="s.loaded" size="small" color="green" class="ml-1">已连接</v-chip>
              </template>
              <template #subtitle>{{ s.command }}</template>
              <template #append>
                <v-btn v-if="s.loaded" icon="mdi-stop" variant="text" color="error" @click="stopMcp(s.name)" />
              </template>
            </v-list-item>
            <v-list-item v-if="!mcpServers.length" title="（无 MCP 服务器）" />
          </v-list>
          <v-divider class="my-3" />
          <h4>添加 MCP 服务器</h4>
          <v-text-field v-model="mcpForm.name" label="name" density="compact" />
          <v-text-field v-model="mcpForm.command" label="command（如 npx）" density="compact" />
          <v-text-field v-model="mcpForm.argsStr" label="args（逗号分隔，如 -y,@snowluma/mcp）" density="compact" />
          <v-text-field v-model="mcpForm.envStr" label="env（key=value 逗号分隔）" density="compact" />
          <v-btn color="primary" @click="addMcp">添加并连接</v-btn>
        </v-card>
      </v-tabs-window-item>

      <!-- Skills -->
      <v-tabs-window-item value="skills">
        <v-card class="mt-4 pa-4">
          <v-list density="compact">
            <v-list-item v-for="s in skills" :key="s.id">
              <template #title>{{ s.name }}</template>
              <template #subtitle>触发词：{{ (s.trigger || []).join('、') }} · {{ s.prompt }}</template>
              <template #append>
                <v-btn icon="mdi-delete" variant="text" color="error" @click="delSkill(s.id)" />
              </template>
            </v-list-item>
            <v-list-item v-if="!skills.length" title="（无技能）" />
          </v-list>
          <v-divider class="my-3" />
          <h4>新建技能</h4>
          <v-text-field v-model="skillForm.name" label="名字" density="compact" />
          <v-text-field v-model="skillForm.trigger" label="触发词（逗号分隔）" density="compact" />
          <v-textarea v-model="skillForm.prompt" label="指令/步骤" rows="2" density="compact" />
          <v-btn color="primary" @click="addSkill">添加</v-btn>
        </v-card>
      </v-tabs-window-item>

      <!-- Plugins -->
      <v-tabs-window-item value="plugins">
        <v-card class="mt-4 pa-4">
          <v-list density="compact">
            <v-list-item v-for="p in plugins" :key="p.name">
              <template #title>
                {{ p.name }}
                <v-chip v-if="p.running" size="small" color="green" class="ml-1">运行中</v-chip>
              </template>
              <template #subtitle>v{{ p.version }} · {{ p.description }}</template>
              <template #append>
                <v-btn v-if="!p.running" icon="mdi-play" variant="text" color="primary" @click="startPlugin(p.name)" />
                <v-btn v-else icon="mdi-stop" variant="text" color="error" @click="stopPlugin(p.name)" />
              </template>
            </v-list-item>
            <v-list-item v-if="!plugins.length" title="（无插件，plugins/ 目录下放 manifest.yaml + main.py 即加载）" />
          </v-list>
        </v-card>
      </v-tabs-window-item>
    </v-tabs-window>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const tab = ref('mcp')
const mcpServers = ref([])
const skills = ref([])
const plugins = ref([])
const mcpForm = ref({ name: '', command: '', argsStr: '', envStr: '' })
const skillForm = ref({ name: '', trigger: '', prompt: '' })

async function loadMcp() { mcpServers.value = (await api.get('/mcp')).data.servers }
async function loadSkills() { skills.value = (await api.get('/skills')).data.skills }
async function loadPlugins() { plugins.value = (await api.get('/plugins')).data.plugins }

async function addMcp() {
  await api.post('/mcp', {
    name: mcpForm.value.name,
    command: mcpForm.value.command,
    args: mcpForm.value.argsStr.split(',').map(s => s.trim()).filter(Boolean),
    env: {},
  })
  mcpForm.value = { name: '', command: '', argsStr: '', envStr: '' }
  await loadMcp()
}
async function stopMcp(name) { await api.post('/mcp/' + name + '/stop'); await loadMcp() }

async function addSkill() {
  await api.post('/skills', skillForm.value)
  skillForm.value = { name: '', trigger: '', prompt: '' }
  await loadSkills()
}
async function delSkill(id) { await api.delete('/skills/' + id); await loadSkills() }

async function startPlugin(name) { await api.post('/plugins/' + name + '/start'); await loadPlugins() }
async function stopPlugin(name) { await api.post('/plugins/' + name + '/stop'); await loadPlugins() }

onMounted(() => { loadMcp(); loadSkills(); loadPlugins() })
</script>
