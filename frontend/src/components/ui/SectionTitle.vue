<template>
  <h3 class="dash-section-title">
    <component v-if="typeof icon !== 'string'" :is="icon" class="section-icon" />
    <span v-else class="section-icon-text">{{ icon }}</span>
    <span class="section-text">{{ title }}</span>
  </h3>
</template>

<script setup>
defineProps({
  icon: [String, Object, Function],
  title: String
})
</script>

<style scoped>
.dash-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  margin-bottom: 16px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-h);
}

.section-icon {
  width: 20px;
  height: 20px;
  color: var(--accent);
}

.section-icon-text {
  font-size: 20px;
}
</style>
