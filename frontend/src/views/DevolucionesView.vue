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
        <li>Identifica qué productos se devuelven más, para tomar acciones correctivas con vendedores o clientes.</li>
        <li><strong>Observación:</strong> es el texto tal como lo escribió quien hizo la nota crédito en el POS (no se interpreta ni se clasifica, para evitar errores).</li>
        <li><strong>Origen y Vendedor (venta):</strong> se obtienen cruzando la nota crédito con su <em>factura de venta original</em>, así se sabe si la devolución vino de POS o domicilio y quién fue el vendedor real (no quien procesó la nota).</li>
        <li><strong>Autorizada por:</strong> las devoluciones (notas crédito) las crea un administrador o usuario autorizado, no el vendedor de la venta. Por eso el ranking muestra quién <em>procesa/autoriza</em> las devoluciones, útil para control interno.</li>
      </ul>
    </ModuleInfo>


    <div v-if="store.status.notas_credito" class="filters-bar" style="margin-bottom: 16px;">
      <div class="filter-group">
        <label>Fecha Inicio</label>
        <input type="date" v-model="filters.fecha_ini" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label>Fecha Fin</label>
        <input type="date" v-model="filters.fecha_fin" @change="applyFilters" />
      </div>
    </div>

    <div v-if="store.errors.devoluciones" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.devoluciones }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 5" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard :icon="RotateCcw" label="Total Devuelto" :value="store.fmt(data.kpis.total_devuelto)" />
      <KpiCard :icon="Package" label="Unidades Devueltas" :value="store.fmtN(data.kpis.unidades_devueltas)" />
      <KpiCard :icon="Activity" label="Tasa de Devolución" :value="data.kpis.tasa_pct + '%'" />
      <KpiCard :icon="Receipt" label="Notas Emitidas" :value="store.fmtN(data.kpis.n_notas)" />
      <KpiCard :icon="DollarSign" label="Ingreso Neto Real" :value="store.fmt(data.kpis.ingresos_netos)" />
      <KpiCard :icon="Bike" label="% Devuelto de Domicilio" :value="(data.kpis.pct_domicilio ?? 0) + '%'" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><RotateCcw size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Sube el archivo de <strong>Notas Crédito</strong> (y <strong>Ventas</strong>) para habilitar este análisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Tendencia -->
      <div class="card" style="grid-column: span 2;">
        <SectionTitle :icon="TrendingUp" title="Tendencia de Devoluciones" />
        <LineChart v-if="tendCat.length" :categories="tendCat" :series="[{name: 'Devoluciones', data: tendData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay datos suficientes para tendencia.</p>
      </div>

      <!-- POS vs Domicilio (según la venta original) -->
      <div class="card" v-if="origenLabels.length">
        <SectionTitle :icon="Bike" title="Devoluciones por origen: POS vs Domicilio" />
        <DonutChart :labels="origenLabels" :series="origenData" />
        <p style="margin-top:8px;color:var(--fg-muted);font-size:12px;">Según de qué venta vino la devolución (vía la factura original).</p>
      </div>

      <!-- Por vendedor REAL de la venta -->
      <div class="card" v-if="vorCat.length">
        <div class="section-header-row">
          <SectionTitle :icon="Users" title="Top 10 vendedores con más devoluciones (de su venta)" />
          <div class="metric-toggle">
            <button :class="{ active: metric === 'valor' }" @click="metric = 'valor'">Valor</button>
            <button :class="{ active: metric === 'unidades' }" @click="metric = 'unidades'">Unidades</button>
          </div>
        </div>
        <BarChart :horizontal="true" :formatTooltip="metric === 'valor' ? 'currency' : ''" :categories="vorCat" :series="[{name: metricLabel, data: vorData}]" />
        <p style="margin-top:8px;color:var(--fg-muted);font-size:12px;">El vendedor de la venta original que terminó devuelta (no quien procesó la nota).</p>
      </div>

      <!-- Por usuario que autoriza/procesa la devolución -->
      <div class="card">
        <div class="section-header-row">
          <SectionTitle :icon="Users" title="Top 10 usuarios con más devoluciones procesadas" />
          <div class="metric-toggle">
            <button :class="{ active: metric === 'valor' }" @click="metric = 'valor'">Valor</button>
            <button :class="{ active: metric === 'unidades' }" @click="metric = 'unidades'">Unidades</button>
          </div>
        </div>
        <BarChart v-if="vendCat.length" :horizontal="true" :formatTooltip="metric === 'valor' ? 'currency' : ''" :categories="vendCat" :series="[{name: metricLabel, data: vendData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay datos por usuario.</p>
      </div>

      <!-- Por Sede -->
      <div class="card">
        <div class="section-header-row">
          <SectionTitle :icon="Store" title="Devoluciones por Sede" />
          <div class="metric-toggle">
            <button :class="{ active: metric === 'valor' }" @click="metric = 'valor'">Valor</button>
            <button :class="{ active: metric === 'unidades' }" @click="metric = 'unidades'">Unidades</button>
          </div>
        </div>
        <BarChart v-if="sedeCat.length" :horizontal="true" :formatTooltip="metric === 'valor' ? 'currency' : ''" :categories="sedeCat" :series="[{name: metricLabel, data: sedeData}]" />
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
                <th @click="sortBy('Punto Venta')" style="cursor: pointer;">
                  Sede <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Punto Venta' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('OrigenVenta')" style="cursor: pointer;">
                  Origen <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'OrigenVenta' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('OrigenFactura')" style="cursor: pointer;">
                  Factura orig. <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'OrigenFactura' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('VendedorOriginal')" style="cursor: pointer;">
                  Vendedor (venta) <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'VendedorOriginal' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Vendedor')" style="cursor: pointer;">
                  Autorizada por <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Vendedor' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Observaciones')" style="cursor: pointer;">
                  Observación <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Observaciones' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortBy('Unidades')" style="cursor: pointer;">
                  Uds <span style="opacity: 0.5; font-size: 10px;">{{ sortCol === 'Unidades' ? (sortDesc ? '▼' : '▲') : '↕' }}</span>
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
                <td>{{ row['Punto Venta'] || 'N/A' }}</td>
                <td>
                  <span class="badge" :class="row.OrigenVenta === 'Domicilio' ? 'badge-amber' : (row.OrigenVenta === 'POS' ? 'badge-green' : '')">{{ row.OrigenVenta || '—' }}</span>
                </td>
                <td>{{ row.OrigenFactura || '—' }}</td>
                <td>{{ (row.VendedorOriginal || '—').substring(0, 22) }}</td>
                <td>{{ (row.Vendedor || row.Creada || 'N/A').substring(0, 22) }}</td>
                <td :title="row.Observaciones || ''" style="max-width: 280px; white-space: normal; color: var(--fg-muted); font-size: 12px;">
                  {{ row.Observaciones || '—' }}
                </td>
                <td>{{ store.fmtN(row.Unidades || 0) }}</td>
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
import { RotateCcw, Activity, Receipt, DollarSign, TrendingUp, Users, Store, AlertTriangle, ClipboardList, Download, Calendar, Package, Bike } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.devoluciones)
const loading = computed(() => store.loading.devoluciones)
const filters = ref({ fecha_ini: '', fecha_fin: '' })
const metric = ref('valor')
const metricLabel = computed(() => metric.value === 'valor' ? 'Valor Devuelto' : 'Unidades Devueltas')

function applyFilters() {
  const params = {}
  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  store.fetchDevoluciones(params)
}

onMounted(() => {
  if (store.status.notas_credito && !data.value) {
    applyFilters()
  }
})

// Charts data
const tendCat = computed(() => data.value?.tendencia?.map(d => d.fecha) || [])
const tendData = computed(() => data.value?.tendencia?.map(d => d.total) || [])

const vendCat = computed(() => data.value?.por_vendedor?.slice(0,10).map(d => d.vendedor) || [])
const vendData = computed(() => data.value?.por_vendedor?.slice(0,10).map(d => metric.value === 'valor' ? d.total_devuelto : (d.n_unidades || 0)) || [])

const sedeCat = computed(() => data.value?.por_sede?.map(d => d.sede) || [])
const sedeData = computed(() => data.value?.por_sede?.map(d => metric.value === 'valor' ? d.total_devuelto : (d.n_unidades || 0)) || [])

// POS vs Domicilio (origen de la venta)
const origenLabels = computed(() => data.value?.por_origen?.map(d => d.origen) || [])
const origenData = computed(() => data.value?.por_origen?.map(d => d.total_devuelto) || [])

// Vendedor REAL de la venta original
const vorCat = computed(() => data.value?.por_vendedor_original?.slice(0,10).map(d => d.vendedor) || [])
const vorData = computed(() => data.value?.por_vendedor_original?.slice(0,10).map(d => metric.value === 'valor' ? d.total_devuelto : (d.n_unidades || 0)) || [])

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

function exportTable() {
  const cols = [
    { key: 'Fecha', label: 'Fecha', formatter: formatDate },
    { key: 'NotaCredito', label: 'Nota' },
    { key: 'Punto Venta', label: 'Sede' },
    { key: 'OrigenVenta', label: 'Origen (POS/Domicilio)' },
    { key: 'OrigenFactura', label: 'Factura Origen' },
    { key: 'VendedorOriginal', label: 'Vendedor (venta)' },
    { key: 'Vendedor', label: 'Autorizada por' },
    { key: 'Unidades', label: 'Unidades' },
    { key: 'Total Neto', label: 'Devuelto (Sin IVA)' },
    { key: 'Observaciones', label: 'Observaciones' }
  ]
  exportToCSV(sortedTabla.value, cols, 'Detalle_Notas_Credito')
}
</script>

<style scoped>
.metric-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.metric-toggle button {
  background: transparent;
  border: none;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  color: var(--fg-muted);
}
.metric-toggle button.active {
  background: var(--accent);
  color: #fff;
}
</style>
