<template>
  <div class="kpi-card">
    <div class="kpi-icon-wrapper">
      <component v-if="typeof icon !== 'string'" :is="icon" class="kpi-icon-lucide" />
      <span v-else class="kpi-icon">{{ icon }}</span>
    </div>
    <div class="kpi-value">{{ value }}</div>
    <div class="kpi-label">{{ label }}</div>
    <slot name="sub"></slot>
  </div>
</template>

<script setup>
defineProps({
  icon: [String, Object, Function],
  value: [String, Number],
  label: String
})
</script>

<style scoped>
.kpi-card {
  background: var(--bg-card);
  backdrop-filter: var(--card-blur);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 22px 26px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  transition: all 0.3s var(--ease);
}

.kpi-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: var(--shadow-lg), var(--glow-accent);
}

body.light-theme .kpi-card:hover {
  border-color: var(--accent);
}

.kpi-icon-wrapper {
  background: var(--accent-lt);
  color: var(--accent);
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
}

.kpi-icon-lucide {
  width: 20px;
  height: 20px;
  stroke-width: 2.2px;
}

.kpi-value {
  font-family: var(--font-display);
  font-size: 1.7rem;
  font-weight: 800;
  color: var(--fg);
  margin-bottom: 4px;
  line-height: 1.15;
  letter-spacing: -0.5px;
}

.kpi-label {
  font-size: 0.82rem;
  color: var(--fg-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.2px;
}
</style>
