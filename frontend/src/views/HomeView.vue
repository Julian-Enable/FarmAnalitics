<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <LayoutDashboard size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Resumen General</h2>
      </div>
      <p style="margin-top: 8px;">Visión global del rendimiento y salud del negocio</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Ofrecerte una visión "a vista de pájaro" de cómo va la farmacia.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Ingresos y Unidades:</strong> Suma directa de la columna "Ingreso" y "Cant" del archivo de Ventas.</li>
        <li><strong>Utilidad Bruta:</strong> Se calcula restando el "Precio Compra" (tomado del Inventario) al "Precio Venta", multiplicado por las unidades vendidas. Muestra tu ganancia real antes de gastos operativos.</li>
        <li><strong>Ticket Promedio:</strong> Ingresos Totales divididos entre la cantidad de Facturas únicas. Te dice cuánto gasta en promedio cada cliente que entra.</li>
        <li><strong>Tendencia y Sedes:</strong> Gráficos que agrupan los ingresos por fecha (semanalmente) y por cada punto de venta para detectar qué sede vende más.</li>
      </ul>
    </ModuleInfo>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard :icon="DollarSign" label="Ingresos Totales" :value="store.fmt(data.kpis.ingresos)" />
      <KpiCard :icon="TrendingUp" label="Utilidad Bruta" :value="store.fmt(data.kpis.utilidad)" />
      <KpiCard :icon="Percent" label="Margen Promedio" :value="data.kpis.margen_pct != null ? data.kpis.margen_pct + '%' : '—'" />
      <KpiCard :icon="Package" label="Unidades Vendidas" :value="store.fmtN(data.kpis.unidades)" />
      <KpiCard :icon="Receipt" label="Total Facturas" :value="store.fmtN(data.kpis.facturas)" />
      <KpiCard :icon="CreditCard" label="Ticket Promedio" :value="store.fmt(data.kpis.ticket)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><Activity size="48" color="var(--border)" /></div>
      <h3>No hay datos para el resumen</h3>
      <p>Sube tus archivos de ventas e inventario para generar los indicadores.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Tendencia -->
      <div class="card">
        <SectionTitle :icon="LineChartIcon" title="Tendencia de Ingresos" />
        <LineChart v-if="tendenciaCat.length" :categories="tendenciaCat" :series="[{name: 'Ingresos', data: tendenciaData}]" />
        <p v-else class="empty-state" style="padding: 20px;">Datos insuficientes para tendencia</p>
      </div>

      <!-- Sedes -->
      <div class="card">
        <SectionTitle :icon="Store" title="Ingresos por Sede" />
        <BarChart v-if="sedesCat.length" :horizontal="true" formatTooltip="currency" :categories="sedesCat" :series="[{name: 'Ingresos', data: sedesData}]" />
        <p v-else class="empty-state" style="padding: 20px;">Datos insuficientes para sedes</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import LineChart from '../components/charts/LineChart.vue'
import BarChart from '../components/charts/BarChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import { LayoutDashboard, DollarSign, TrendingUp, Percent, Package, Receipt, CreditCard, Activity, LineChart as LineChartIcon, Store } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.resumen)
const loading = computed(() => store.loading.resumen)

onMounted(() => {
  if (store.status.ventas && !data.value) store.fetchResumen()
})

const tendenciaCat = computed(() => data.value?.tendencia?.map(d => d.fecha) || [])
const tendenciaData = computed(() => data.value?.tendencia?.map(d => d.ingreso) || [])

const sedesCat = computed(() => data.value?.sedes?.map(d => d.sede) || [])
const sedesData = computed(() => data.value?.sedes?.map(d => d.ingresos) || [])
</script>
