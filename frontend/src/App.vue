<template>
  <div id="app">
    <AppSidebar />
    <main class="main">
      <div v-if="store.lastError" class="app-error-banner">
        {{ store.lastError }}
      </div>
      <router-view v-if="isStatusLoaded" v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
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
