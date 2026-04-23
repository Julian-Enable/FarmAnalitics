<template>
  <div class="module-info">
    <div class="info-header" @click="isOpen = !isOpen">
      <span class="info-icon">💡</span>
      <span class="info-title">¿Qué hace este módulo y cómo se calcula?</span>
      <span class="info-toggle">{{ isOpen ? '▲ Ocultar' : '▼ Leer más' }}</span>
    </div>
    <transition name="slide-fade">
      <div v-if="isOpen" class="info-body">
        <slot></slot>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const isOpen = ref(false)
</script>

<style scoped>
.module-info {
  background: var(--accent-lt);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  margin-bottom: 24px;
  overflow: hidden;
}

.info-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  background: rgba(94, 106, 210, 0.05);
  transition: background 0.2s ease;
}

.info-header:hover {
  background: rgba(94, 106, 210, 0.1);
}

.info-icon {
  font-size: 1.2rem;
  margin-right: 12px;
}

.info-title {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--accent-dk);
}

.info-toggle {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent);
}

.info-body {
  padding: 16px;
  border-top: 1px solid rgba(94, 106, 210, 0.2);
  font-size: 0.82rem;
  color: var(--fg);
  line-height: 1.6;
  background: #ffffff;
}

/* Transiciones */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.2s cubic-bezier(1, 0.5, 0.8, 1);
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}
</style>
