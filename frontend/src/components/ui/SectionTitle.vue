<template>
  <h3 class="dash-section-title" style="margin-top: 8px;">
    {{ icon }} &nbsp;{{ title }}
  </h3>
</template>

<script setup>
defineProps({
  icon: String,
  title: String
})
</script>
