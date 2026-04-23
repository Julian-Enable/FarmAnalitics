<template>
  <apexchart :type="horizontal ? 'bar' : 'column'" height="350" :options="chartOptions" :series="series"></apexchart>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  categories: { type: Array, required: true },
  series: { type: Array, required: true },
  horizontal: { type: Boolean, default: false },
  formatTooltip: { type: String, default: 'number' } // 'number' or 'currency'
})

const chartOptions = computed(() => ({
  chart: {
    fontFamily: 'Inter, sans-serif',
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeinout', speed: 800 }
  },
  colors: ['#5E6AD2', '#10B981', '#EF4444', '#F59E0B'],
  plotOptions: {
    bar: {
      horizontal: props.horizontal,
      columnWidth: '50%',
      borderRadius: 4
    }
  },
  dataLabels: { enabled: false },
  stroke: { show: true, width: 2, colors: ['transparent'] },
  xaxis: {
    categories: props.categories,
    labels: { 
      style: { colors: '#6B7280', fontSize: '11px' },
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
      style: { colors: '#6B7280', fontSize: '11px' },
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
    borderColor: '#E5E7EB',
    strokeDashArray: 4,
  },
  fill: { opacity: 1 },
  tooltip: {
    theme: 'light',
    y: {
      formatter: function (val) {
        if (props.formatTooltip === 'currency') return "$" + val.toLocaleString('es-CO')
        return val.toLocaleString('es-CO')
      }
    }
  }
}))
</script>
