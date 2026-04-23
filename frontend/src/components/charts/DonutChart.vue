<template>
  <apexchart type="donut" height="350" :options="chartOptions" :series="series"></apexchart>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  labels: { type: Array, required: true },
  series: { type: Array, required: true }
})

const chartOptions = computed(() => ({
  chart: {
    fontFamily: 'Inter, sans-serif',
    animations: { enabled: true, easing: 'easeinout', speed: 800 }
  },
  labels: props.labels,
  colors: ['#5E6AD2', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'],
  dataLabels: {
    enabled: true,
    formatter: function (val) {
      return val.toFixed(1) + "%"
    }
  },
  plotOptions: {
    pie: {
      donut: {
        size: '65%'
      }
    }
  },
  stroke: { show: true, colors: ['#ffffff'], width: 2 },
  legend: {
    position: 'bottom',
    horizontalAlign: 'center',
    labels: { colors: '#374151' }
  },
  tooltip: {
    theme: 'light',
    y: {
      formatter: function (val) {
        return val.toLocaleString('es-CO')
      }
    }
  }
}))
</script>
