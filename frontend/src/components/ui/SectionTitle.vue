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
  gap: 10px;
  margin-top: 4px;
  margin-bottom: 20px;
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--fg);
  letter-spacing: -0.3px;
}

.section-icon {
  width: 20px;
  height: 20px;
  color: var(--accent);
  stroke-width: 2.2px;
}

.section-icon-text {
  font-size: 1.25rem;
}
</style>
