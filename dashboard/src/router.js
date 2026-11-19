import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/Login.vue') },
  { path: '/', name: 'overview', component: () => import('./views/Overview.vue') },
  { path: '/providers', name: 'providers', component: () => import('./views/Providers.vue') },
  { path: '/tools', name: 'tools', component: () => import('./views/Tools.vue') },
  { path: '/personas', name: 'personas', component: () => import('./views/Persona.vue') },
  { path: '/extensions', name: 'extensions', component: () => import('./views/Extensions.vue') },
  { path: '/permissions', name: 'permissions', component: () => import('./views/Permissions.vue') },
  { path: '/conversations', name: 'conversations', component: () => import('./views/Conversations.vue') },
  { path: '/reminders', name: 'reminders', component: () => import('./views/Reminders.vue') },
  { path: '/kb', name: 'kb', component: () => import('./views/KnowledgeBase.vue') },
  { path: '/chat', name: 'chat', component: () => import('./views/Chat.vue') },
  { path: '/logs', name: 'logs', component: () => import('./views/Logs.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('lumina_token')
  if (!token && to.path !== '/login') return '/login'
  if (token && to.path === '/login') return '/'
})

export default router
