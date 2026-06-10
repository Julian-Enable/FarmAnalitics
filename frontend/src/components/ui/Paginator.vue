<template>
  <div class="paginator-container" v-if="totalPages > 1">
    <div class="paginator-info">
      Mostrando <strong>{{ startIndex + 1 }}</strong> a <strong>{{ endIndex }}</strong> de <strong>{{ totalItems }}</strong> registros
    </div>
    
    <div class="paginator-controls">
      <button 
        class="page-btn" 
        :disabled="modelValue === 1"
        @click="changePage(modelValue - 1)"
      >
        <ChevronLeft size="15" />
      </button>
      
      <div class="page-numbers">
        <button 
          v-for="page in visiblePages" 
          :key="page"
          class="page-btn"
          :class="{ active: modelValue === page }"
          @click="changePage(page)"
        >
          {{ page }}
        </button>
      </div>

      <button 
        class="page-btn" 
        :disabled="modelValue === totalPages"
        @click="changePage(modelValue + 1)"
      >
        <ChevronRight size="15" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  modelValue: {
    type: Number,
    required: true
  },
  totalItems: {
    type: Number,
    required: true
  },
  itemsPerPage: {
    type: Number,
    default: 10
  }
})

const emit = defineEmits(['update:modelValue'])

const totalPages = computed(() => Math.ceil(props.totalItems / props.itemsPerPage))

const startIndex = computed(() => (props.modelValue - 1) * props.itemsPerPage)
const endIndex = computed(() => Math.min(startIndex.value + props.itemsPerPage, props.totalItems))

const visiblePages = computed(() => {
  const current = props.modelValue
  const total = totalPages.value
  const delta = 2 // páginas a mostrar a los lados de la actual

  let start = Math.max(1, current - delta)
  let end = Math.min(total, current + delta)

  if (current - delta <= 1) {
    end = Math.min(total, start + delta * 2)
  }
  if (current + delta >= total) {
    start = Math.max(1, end - delta * 2)
  }

  const pages = []
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }
  return pages
})

function changePage(page) {
  if (page >= 1 && page <= totalPages.value) {
    emit('update:modelValue', page)
  }
}
</script>

<style scoped>
.paginator-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 0 0;
  margin-top: 16px;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
}

.paginator-info {
  color: var(--fg-muted);
}
.paginator-info strong {
  color: var(--fg);
}

.paginator-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.page-numbers {
  display: flex;
  gap: 4px;
}

.page-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--fg-muted);
  cursor: pointer;
  transition: all 0.2s var(--ease);
  font-family: var(--font-display);
  font-size: 0.88rem;
  font-weight: 700;
}

body.light-theme .page-btn {
  background: rgba(0, 0, 0, 0.02);
}

.page-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--fg);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: var(--glow-accent);
}

body.light-theme .page-btn:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.05);
}

.page-btn.active {
  background: var(--accent-gradient);
  color: white;
  border-color: var(--accent);
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.25);
}

.page-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}
</style>
