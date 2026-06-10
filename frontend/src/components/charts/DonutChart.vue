<template>
  <apexchart type="donut" height="350" :options="chartOptions" :series="series"></apexchart>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../../stores/dashboard'

const store = useDashboardStore()

const props = defineProps({
  labels: { type: Array, required: true },
  series: { type: Array, required: true }
})

const chartOptions = computed(() => ({
  chart: {
    fontFamily: 'var(--font-body)',
    background: 'transparent',
    animations: { enabled: true, easing: 'easeinout', speed: 800 }
  },
  labels: props.labels,
  colors: ['#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#a855f7'],
  dataLabels: {
    enabled: true,
    formatter: function (val) {
      return val.toFixed(1) + "%"
    },
    style: {
      fontFamily: 'var(--font-body)',
      fontWeight: 700
    }
  },
  plotOptions: {
    pie: {
      donut: {
        size: '65%'
      }
    }
  },
  stroke: { 
    show: true, 
    colors: [store.theme === 'dark' ? '#0f162a' : '#ffffff'], 
    width: 2 
  },
  legend: {
    position: 'bottom',
    horizontalAlign: 'center',
    labels: { 
      colors: store.theme === 'dark' ? '#9ca3af' : '#4b5563',
      fontFamily: 'var(--font-body)'
    }
  },
  tooltip: {
    theme: store.theme,
    y: {
      formatter: function (val) {
        return val.toLocaleString('es-CO')
      }
    }
  }
}))
</script>
