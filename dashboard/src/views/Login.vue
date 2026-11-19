<template>
  <v-main class="d-flex align-center justify-center" style="min-height: 100vh">
    <v-card width="400" class="pa-6">
      <v-card-title class="text-center">Lumina 管理台</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="password"
          type="password"
          label="管理员密码"
          prepend-icon="mdi-lock"
          @keyup.enter="login"
        />
      </v-card-text>
      <v-card-actions>
        <v-btn block color="primary" :loading="loading" @click="login">登录</v-btn>
      </v-card-actions>
    </v-card>
  </v-main>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const password = ref('')
const loading = ref(false)
const router = useRouter()

async function login() {
  loading.value = true
  try {
    const { data } = await api.post('/login', { password: password.value })
    localStorage.setItem('lumina_token', data.token)
    router.push('/')
  } catch (e) {
    alert('密码错误')
  } finally {
    loading.value = false
  }
}
</script>
