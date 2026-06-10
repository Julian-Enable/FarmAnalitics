<template>
  <apexchart :type="horizontal ? 'bar' : 'column'" height="350" :options="chartOptions" :series="series"></apexchart>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../../stores/dashboard'

const store = useDashboardStore()

const props = defineProps({
  categories: { type: Array, required: true },
  series: { type: Array, required: true },
  horizontal: { type: Boolean, default: false },
  formatTooltip: { type: String, default: 'number' } // 'number' or 'currency'
})

const chartOptions = computed(() => ({
  chart: {
    fontFamily: 'var(--font-body)',
    background: 'transparent',
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeinout', speed: 800 }
  },
  colors: ['#6366f1', '#10b981', '#f43f5e', '#f59e0b'],
  plotOptions: {
    bar: {
      horizontal: props.horizontal,
      columnWidth: '50%',
      borderRadius: 6
    }
  },
  dataLabels: { enabled: false },
  stroke: { show: true, width: 2, colors: ['transparent'] },
  xaxis: {
    categories: props.categories,
    labels: { 
      style: { 
        colors: store.theme === 'dark' ? '#9ca3af' : '#4b5563', 
        fontSize: '11px',
        fontFamily: 'var(--font-body)',
        fontWeight: 500
      },
      formatter: function(val) {
        if (typeof val === 'number') {
          if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M'
          if (val >= 1000) return (val / 1000).toFixed(1) + 'K'
        }
        return val
      }
    }
  },
  yaxis: {
    labels: { 
      style: { 
        colors: store.theme === 'dark' ? '#9ca3af' : '#4b5563', 
        fontSize: '11px',
        fontFamily: 'var(--font-body)',
        fontWeight: 500
      },
      formatter: function(val) {
        if (typeof val === 'number') {
          if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M'
          if (val >= 1000) return (val / 1000).toFixed(1) + 'K'
        }
        return val
      }
    }
  },
  grid: {
    borderColor: store.theme === 'dark' ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.08)',
    strokeDashArray: 4,
  },
  fill: { opacity: 1 },
  tooltip: {
    theme: store.theme,
    y: {
      formatter: function (val) {
        if (props.formatTooltip === 'currency') return "$" + val.toLocaleString('es-CO')
        return val.toLocaleString('es-CO')
      }
    }
  }
}))
</script>
