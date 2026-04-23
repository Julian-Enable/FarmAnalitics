<template>
  <apexchart type="line" height="350" :options="chartOptions" :series="series"></apexchart>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  categories: { type: Array, required: true },
  series: { type: Array, required: true },
  title: String,
  yLabel: String
})

const chartOptions = computed(() => ({
  chart: {
    fontFamily: 'Inter, sans-serif',
    toolbar: { show: false },
    zoom: { enabled: false },
    animations: { enabled: true, easing: 'easeinout', speed: 800 }
  },
  colors: ['#5E6AD2', '#10B981', '#F59E0B'],
  stroke: { curve: 'smooth', width: 3 },
  xaxis: {
    categories: props.categories,
    tickAmount: 10,
    labels: { 
      style: { colors: '#6B7280', fontSize: '11px' },
      rotate: -45,
      rotateAlways: false,
      hideOverlappingLabels: true,
      formatter: function(val) {
        // Truncate long labels slightly if they are not dates
        if (typeof val === 'string' && val.length > 15) return val.substring(0, 15) + '...'
        return val
      }
    },
    axisBorder: { show: false },
    axisTicks: { show: false }
  },
  yaxis: {
    labels: {
      style: { colors: '#6B7280', fontSize: '12px' },
      formatter: (value) => {
        if (value >= 1000000) return '$' + (value / 1000000).toFixed(1) + 'M'
        if (value >= 1000) return '$' + (value / 1000).toFixed(0) + 'k'
        return value
      }
    }
  },
  grid: {
    borderColor: '#E5E7EB',
    strokeDashArray: 4,
    xaxis: { lines: { show: true } },
    yaxis: { lines: { show: true } }
  },
  dataLabels: { enabled: false },
  tooltip: {
    theme: 'light',
    y: {
      formatter: function (val) {
        return "$" + val.toLocaleString('es-CO')
      }
    }
  }
}))
</script>
