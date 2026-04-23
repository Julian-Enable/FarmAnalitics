<template>
  <div class="kpi-card">
    <div class="kpi-icon">{{ icon }}</div>
    <div class="kpi-value">{{ value }}</div>
    <div class="kpi-label">{{ label }}</div>
  </div>
</template>

<script setup>
defineProps({
  icon: String,
  value: [String, Number],
  label: String
})
</script>
