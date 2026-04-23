<template>
  <div class="kpi-card">
    <div class="kpi-icon-wrapper">
      <component v-if="typeof icon === 'object'" :is="icon" class="kpi-icon-lucide" />
      <span v-else class="kpi-icon">{{ icon }}</span>
    </div>
    <div class="kpi-value">{{ value }}</div>
    <div class="kpi-label">{{ label }}</div>
  </div>
</template>

<script setup>
defineProps({
  icon: [String, Object],
  value: [String, Number],
  label: String
})
</script>

<style scoped>
.kpi-card {
  background: var(--social-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  transition: transform 0.2s, box-shadow 0.2s;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.kpi-icon-wrapper {
  background: var(--accent-bg);
  color: var(--accent);
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.kpi-icon-lucide {
  width: 22px;
  height: 22px;
}

.kpi-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-h);
  margin-bottom: 4px;
}

.kpi-label {
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
}
</style>
