<template>
  <apexchart type="line" height="350" :options="chartOptions" :series="series"></apexchart>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../../stores/dashboard'

const store = useDashboardStore()

const props = defineProps({
  categories: { type: Array, required: true },
  series: { type: Array, required: true },
  title: String,
  yLabel: String
})

const chartOptions = computed(() => ({
  chart: {
    fontFamily: 'var(--font-body)',
    background: 'transparent',
    toolbar: { show: false },
    zoom: { enabled: false },
    animations: { enabled: true, easing: 'easeinout', speed: 800 }
  },
  colors: ['#6366f1', '#10b981', '#f59e0b'],
  stroke: { curve: 'smooth', width: 3 },
  xaxis: {
    categories: props.categories,
    tickAmount: 10,
    labels: { 
      style: { 
        colors: store.theme === 'dark' ? '#9ca3af' : '#4b5563', 
        fontSize: '11px',
        fontFamily: 'var(--font-body)',
        fontWeight: 500
      },
      rotate: -45,
      rotateAlways: false,
      hideOverlappingLabels: true,
      formatter: function(val) {
        if (typeof val === 'string' && val.length > 15) return val.substring(0, 15) + '...'
        return val
      }
    },
    axisBorder: { show: false },
    axisTicks: { show: false }
  },
  yaxis: {
    labels: {
      style: { 
        colors: store.theme === 'dark' ? '#9ca3af' : '#4b5563', 
        fontSize: '12px',
        fontFamily: 'var(--font-body)',
        fontWeight: 500
      },
      formatter: (value) => {
        if (value >= 1000000) return '$' + (value / 1000000).toFixed(1) + 'M'
        if (value >= 1000) return '$' + (value / 1000).toFixed(0) + 'k'
        return value
      }
    }
  },
  grid: {
    borderColor: store.theme === 'dark' ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.08)',
    strokeDashArray: 4,
    xaxis: { lines: { show: true } },
    yaxis: { lines: { show: true } }
  },
  dataLabels: { enabled: false },
  tooltip: {
    theme: store.theme,
    y: {
      formatter: function (val) {
        return "$" + val.toLocaleString('es-CO')
      }
    }
  }
}))
</script>
