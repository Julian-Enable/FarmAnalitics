<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <Store size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Rendimiento por Sedes</h2>
      </div>
      <p style="margin-top: 8px;">Comparativo de métricas clave entre puntos de venta</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Comparar el rendimiento comercial entre tus diferentes sucursales para fomentar la competitividad y detectar puntos débiles.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Ingresos y Unidades por Sede:</strong> Agrupa todas las ventas del archivo basándose en la columna "Punto Venta".</li>
        <li><strong>Ticket Promedio por Sede:</strong> Calcula cuánto se gasta en promedio por cada factura emitida en esa sede específica. Útil para medir si los asesores de esa sucursal están haciendo "venta cruzada".</li>
        <li><strong>Top 5 por Sede:</strong> Al seleccionar una sucursal en el filtro, te muestra qué es lo que más se vende allí específicamente.</li>
      </ul>
    </ModuleInfo>

    <!-- Filtros -->
    <div v-if="data" class="filters-bar">
      <div class="filter-group">
        <label>Seleccionar Sede para Detalle</label>
        <select v-model="filters.sede_detalle" @change="applyFilters">
          <option value="">(Ninguna)</option>
          <option v-for="s in data.lista_sedes" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Fecha Inicio</label>
        <input type="date" v-model="filters.fecha_ini" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label>Fecha Fin</label>
        <input type="date" v-model="filters.fecha_fin" @change="applyFilters" />
      </div>
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-3">
      <div v-for="i in 3" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-3">
      <KpiCard :icon="Store" label="Total Sedes" :value="data.comparativo.length" />
      <KpiCard :icon="DollarSign" label="Sede Mayor Ingreso" :value="data.comparativo[0]?.sede || '—'" />
      <KpiCard :icon="TrendingUp" label="Ingreso Promedio por Sede" :value="store.fmt(promedioIngresos)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><Store size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Sube archivos de **Ventas** para comparar el rendimiento de las sedes.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Ingresos -->
      <div class="card">
        <SectionTitle :icon="DollarSign" title="Ingresos por Sede" />
        <BarChart v-if="sedesCat.length" :horizontal="true" formatTooltip="currency" :categories="sedesCat" :series="[{name: 'Ingresos', data: sedesIngresos}]" />
      </div>

      <!-- Tabla Comparativa -->
      <div class="card">
        <div class="section-header-row">
          <SectionTitle :icon="BarChart2" title="Métricas por Sede" />
          <button class="export-btn" @click="exportSedes" v-if="data.comparativo.length">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
        <div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Sede</th>
                <th>Ingresos</th>
                <th>Unidades</th>
                <th>Ticket Prom.</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.comparativo" :key="row.sede">
                <td><strong>{{ row.sede }}</strong></td>
                <td>{{ store.fmt(row.ingresos) }}</td>
                <td>{{ store.fmtN(row.unidades) }}</td>
                <td>{{ store.fmt(row.ticket) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="data && filters.sede_detalle" class="grid-2" style="margin-top: 16px;">
      <!-- Top 5 Sede Seleccionada -->
      <div class="card">
        <SectionTitle :icon="Trophy" :title="`Top 5 Productos en: ${filters.sede_detalle}`" />
        <BarChart v-if="top5Cat.length" :horizontal="true" :categories="top5Cat" :series="[{name: 'Unidades', data: top5Data}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay ventas para esta sede.</p>
      </div>

      <!-- Info Adicional Sede -->
      <div class="card" v-if="detalleInfo">
        <SectionTitle :icon="Pin" :title="`Resumen: ${filters.sede_detalle}`" />
        <div style="margin-top: 20px;">
          <div style="margin-bottom: 12px;">
            <div style="color: var(--fg-muted); font-size: 0.8rem; font-weight: 500;">Ingresos Totales</div>
            <div style="font-size: 1.5rem; font-weight: 700;">{{ store.fmt(detalleInfo.ingresos) }}</div>
          </div>
          <div style="margin-bottom: 12px;">
            <div style="color: var(--fg-muted); font-size: 0.8rem; font-weight: 500;">Unidades Vendidas</div>
            <div style="font-size: 1.5rem; font-weight: 700;">{{ store.fmtN(detalleInfo.unidades) }}</div>
          </div>
          <div style="margin-bottom: 12px;">
            <div style="color: var(--fg-muted); font-size: 0.8rem; font-weight: 500;">Stock Actual (Si aplica)</div>
            <div style="font-size: 1.5rem; font-weight: 700;">{{ store.fmtN(data.stock_sedes[filters.sede_detalle]) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import BarChart from '../components/charts/BarChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import { exportToCSV } from '../utils/export'
import { Store, DollarSign, TrendingUp, BarChart2, Trophy, Pin, Download } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.sedes)
const loading = computed(() => store.loading.sedes)

const filters = ref({
  sede_detalle: '',
  fecha_ini: '',
  fecha_fin: ''
})

function applyFilters() {
  const params = { ...filters.value }
  if (!params.sede_detalle) delete params.sede_detalle
  if (!params.fecha_ini) delete params.fecha_ini
  if (!params.fecha_fin) delete params.fecha_fin
  store.fetchSedes(params)
}

onMounted(() => {
  if (store.status.ventas && !data.value) {
    applyFilters()
  }
})

const promedioIngresos = computed(() => {
  if (!data.value || !data.value.comparativo.length) return 0
  const total = data.value.comparativo.reduce((acc, curr) => acc + curr.ingresos, 0)
  return total / data.value.comparativo.length
})

const sedesCat = computed(() => data.value?.comparativo?.map(d => d.sede) || [])
const sedesIngresos = computed(() => data.value?.comparativo?.map(d => d.ingresos) || [])

const top5Cat = computed(() => data.value?.top5_sede?.map(d => d.nombre) || [])
const top5Data = computed(() => data.value?.top5_sede?.map(d => d.Cant) || [])

const detalleInfo = computed(() => {
  if (!data.value || !filters.value.sede_detalle) return null
  return data.value.comparativo.find(d => d.sede === filters.value.sede_detalle)
})

// Exportación
function exportSedes() {
  const cols = [
    { key: 'sede', label: 'Sede' },
    { key: 'ingresos', label: 'Ingresos Totales' },
    { key: 'unidades', label: 'Unidades Vendidas' },
    { key: 'ticket', label: 'Ticket Promedio' }
  ]
  exportToCSV(data.value.comparativo, cols, 'Metricas_Sedes')
}
</script>
