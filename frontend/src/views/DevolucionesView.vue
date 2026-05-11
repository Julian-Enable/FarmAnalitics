<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <RotateCcw size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Devoluciones (Notas Crédito)</h2>
      </div>
      <p style="margin-top: 8px;">Análisis de notas crédito, motivos de devolución y su impacto en el ingreso neto</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Qué significa esto?</strong> Las notas crédito representan ventas anuladas o productos devueltos.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Ingreso Neto:</strong> Ingreso Bruto - Total Devuelto.</li>
        <li><strong>Tasa de Devolución:</strong> Porcentaje de los ingresos que se devolvió (idealmente &lt; 2%).</li>
        <li>Identifica qué productos se devuelven más y por qué, para tomar acciones correctivas con vendedores o clientes.</li>
      </ul>
    </ModuleInfo>

    <div v-if="store.errors.devoluciones" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.devoluciones }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard :icon="RotateCcw" label="Total Devuelto" :value="store.fmt(data.kpis.total_devuelto)" />
      <KpiCard :icon="Activity" label="Tasa de Devolución" :value="data.kpis.tasa_pct + '%'" />
      <KpiCard :icon="Receipt" label="Notas Emitidas" :value="store.fmtN(data.kpis.n_notas)" />
      <KpiCard :icon="DollarSign" label="Ingreso Neto Real" :value="store.fmt(data.kpis.ingresos_netos)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><RotateCcw size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Sube el archivo de **Notas Crédito** (y **Ventas**) para habilitar este análisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Tendencia -->
      <div class="card">
        <SectionTitle :icon="TrendingUp" title="Tendencia de Devoluciones" />
        <LineChart v-if="tendCat.length" :categories="tendCat" :series="[{name: 'Devoluciones', data: tendData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay datos suficientes para tendencia.</p>
      </div>

      <!-- Motivos -->
      <div class="card">
        <SectionTitle :icon="PieChartIcon" title="Motivos de Devolución" />
        <DonutChart v-if="motivoCat.length" :labels="motivoCat" :series="motivoData" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay motivos categorizados.</p>
      </div>

      <!-- Por Vendedor -->
      <div class="card">
        <SectionTitle :icon="Users" title="Top 10 Vendedores con más devoluciones" />
        <BarChart v-if="vendCat.length" :horizontal="true" formatTooltip="currency" :categories="vendCat" :series="[{name: 'Valor Devuelto', data: vendData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay datos por vendedor.</p>
      </div>

      <!-- Por Sede -->
      <div class="card">
        <SectionTitle :icon="Store" title="Devoluciones por Sede" />
        <BarChart v-if="sedeCat.length" :horizontal="true" formatTooltip="currency" :categories="sedeCat" :series="[{name: 'Valor Devuelto', data: sedeData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay datos por sede.</p>
      </div>

      <!-- Top Productos Devueltos -->
      <div class="card" style="grid-column: span 2;" v-if="data.top_productos_devueltos?.length">
        <SectionTitle :icon="AlertTriangle" title="Top 15 Productos más devueltos (Cruce con Ventas)" />
        <BarChart :horizontal="true" formatTooltip="currency" 
                  :categories="data.top_productos_devueltos.map(d => d.nombre)" 
                  :series="[{name: 'Valor Devuelto', data: data.top_productos_devueltos.map(d => d.ingreso_devuelto)}]" />
      </div>

      <!-- Tabla Detalle -->
      <div class="card" style="grid-column: span 2;">
        <div class="section-header-row">
          <SectionTitle :icon="ClipboardList" title="Detalle de Notas Crédito" />
          <button class="export-btn" @click="exportTable">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
        <div style="overflow-x: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th @click="sortBy('Fecha')" style="cursor: pointer;">
                  Fecha <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Fecha' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('NotaCredito')" style="cursor: pointer;">
                  Nota <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'NotaCredito' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Motivo')" style="cursor: pointer;">
                  Motivo <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Motivo' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Punto Venta')" style="cursor: pointer;">
                  Sede <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Punto Venta' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Creada')" style="cursor: pointer;">
                  Vendedor <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Creada' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Factura')" style="cursor: pointer;">
                  Factura Orig. <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Factura' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Total Neto')" style="cursor: pointer;">
                  Total Devuelto (Sin IVA) <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Total Neto' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in paginatedTabla" :key="row.NotaCredito">
                <td>{{ formatDate(row.Fecha) }}</td>
                <td>{{ row.NotaCredito }}</td>
                <td>
                  <span class="badge" :class="getMotivoClass(row.Motivo)">{{ row.Motivo }}</span>
                </td>
                <td>{{ row['Punto Venta'] || 'N/A' }}</td>
                <td>{{ row.Creada?.substring(0, 20) || 'N/A' }}</td>
                <td>{{ row.Factura || 'N/A' }}</td>
                <td style="font-weight: 600; color: var(--red);">{{ store.fmt(row['Total Neto']) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Paginator 
          v-model="page" 
          :totalItems="sortedTabla.length" 
          :itemsPerPage="itemsPerPage" 
        />
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
import LineChart from '../components/charts/LineChart.vue'
import DonutChart from '../components/charts/DonutChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import Paginator from '../components/ui/Paginator.vue'
import { exportToCSV } from '../utils/export'
import { RotateCcw, Activity, Receipt, DollarSign, TrendingUp, PieChart as PieChartIcon, Users, Store, AlertTriangle, ClipboardList, Download } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.devoluciones)
const loading = computed(() => store.loading.devoluciones)

onMounted(() => {
  if (store.status.notas_credito && !data.value) {
    store.fetchDevoluciones()
  }
})

// Charts data
const tendCat = computed(() => data.value?.tendencia?.map(d => d.fecha) || [])
const tendData = computed(() => data.value?.tendencia?.map(d => d.total) || [])

const motivoCat = computed(() => data.value?.por_motivo?.map(d => d.Motivo) || [])
const motivoData = computed(() => data.value?.por_motivo?.map(d => d.total) || [])

const vendCat = computed(() => data.value?.por_vendedor?.slice(0,10).map(d => d.vendedor) || [])
const vendData = computed(() => data.value?.por_vendedor?.slice(0,10).map(d => d.total_devuelto) || [])

const sedeCat = computed(() => data.value?.por_sede?.map(d => d.sede) || [])
const sedeData = computed(() => data.value?.por_sede?.map(d => d.total_devuelto) || [])

// Table Sort & Paginate
const sortCol = ref('Fecha')
const sortDesc = ref(true)
function sortBy(col) {
  if (sortCol.value === col) sortDesc.value = !sortDesc.value
  else { sortCol.value = col; sortDesc.value = true }
}

const sortedTabla = computed(() => {
  const list = data.value?.tabla ? [...data.value.tabla] : []
  if (sortCol.value) {
    list.sort((a, b) => {
      let valA = a[sortCol.value]
      let valB = b[sortCol.value]
      if (typeof valA === 'string') valA = valA.toLowerCase()
      if (typeof valB === 'string') valB = valB.toLowerCase()
      if (valA < valB) return sortDesc.value ? 1 : -1
      if (valA > valB) return sortDesc.value ? -1 : 1
      return 0
    })
  }
  return list
})

const itemsPerPage = 10
const page = ref(1)
const paginatedTabla = computed(() => {
  const start = (page.value - 1) * itemsPerPage
  return sortedTabla.value.slice(start, start + itemsPerPage)
})

function formatDate(timestamp) {
  if (!timestamp) return 'N/A'
  const d = new Date(timestamp)
  return d.toLocaleDateString()
}

function getMotivoClass(motivo) {
  if (motivo === 'Solicitud del Cliente') return 'badge-amber'
  if (motivo === 'Error de Facturación' || motivo === 'Error del Vendedor') return 'badge-red'
  if (motivo === 'Cambio de Producto') return 'badge-green'
  return ''
}

function exportTable() {
  const cols = [
    { key: 'Fecha', label: 'Fecha', formatter: formatDate },
    { key: 'NotaCredito', label: 'Nota' },
    { key: 'Motivo', label: 'Motivo' },
    { key: 'Punto Venta', label: 'Sede' },
    { key: 'Creada', label: 'Vendedor' },
    { key: 'Factura', label: 'Factura Original' },
    { key: 'Total Neto', label: 'Devuelto (Sin IVA)' },
    { key: 'Observaciones', label: 'Observaciones' }
  ]
  exportToCSV(sortedTabla.value, cols, 'Detalle_Notas_Credito')
}
</script>
