<template>
  <div id="app">
    <template v-if="isStatusLoaded">
      <AppSidebar />
      <main class="main">
        <div v-if="store.lastError" class="app-error-banner">
          {{ store.lastError }}
        </div>
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </template>

    <div v-else class="app-boot">
      <div class="app-boot-panel">
        <div class="app-boot-spinner"></div>
        <strong>Farma Analytics</strong>
        <span>Cargando informacion...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import { useDashboardStore } from './stores/dashboard'

const store = useDashboardStore()
const isStatusLoaded = ref(false)
onMounted(async () => {
  await store.checkStatus()
  isStatusLoaded.value = true
})
</script>
