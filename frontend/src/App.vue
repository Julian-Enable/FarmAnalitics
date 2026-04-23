<template>
  <div id="app">
    <AppSidebar />
    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import { useDashboardStore } from './stores/dashboard'

const store = useDashboardStore()
onMounted(() => store.checkStatus())
</script>
