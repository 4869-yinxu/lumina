<template>
  <v-app>
    <v-navigation-drawer v-if="showNav" :rail="rail" permanent>
      <v-list nav density="comfortable">
        <v-list-item
          :prepend-avatar="undefined"
          prepend-icon="mdi-robot"
          :title="rail ? '' : 'lumina'"
          :subtitle="rail ? '' : '管理台'"
        />
        <v-divider />
        <v-list-item
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          :value="item.to"
        />
      </v-list>
    </v-navigation-drawer>

    <v-app-bar v-if="showNav" color="primary" density="comfortable">
      <v-app-bar-nav-icon v-if="!$vuetify.display.mobile" @click="rail = !rail" />
      <v-app-bar-title>Lumina 管理台</v-app-bar-title>
      <v-spacer />
      <v-btn icon="mdi-logout" @click="logout" />
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const rail = ref(false)

const showNav = computed(() => route.path !== '/login')

const nav = [
  { to: '/', title: '概览', icon: 'mdi-view-dashboard' },
  { to: '/providers', title: '供应商', icon: 'mdi-server' },
  { to: '/tools', title: '工具', icon: 'mdi-tools' },
  { to: '/personas', title: '人设', icon: 'mdi-account-cog' },
  { to: '/extensions', title: '扩展', icon: 'mdi-puzzle' },
  { to: '/permissions', title: '权限', icon: 'mdi-shield-account' },
  { to: '/conversations', title: '对话记录', icon: 'mdi-message-text' },
  { to: '/reminders', title: '定时任务', icon: 'mdi-clock-outline' },
  { to: '/kb', title: '知识库', icon: 'mdi-database' },
  { to: '/chat', title: '聊天测试', icon: 'mdi-chat' },
  { to: '/logs', title: '日志', icon: 'mdi-console' },
]

function logout() {
  localStorage.removeItem('lumina_token')
  router.push('/login')
}
</script>
