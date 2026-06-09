<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <DollarSign size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Rentabilidad y Margenes</h2>
      </div>
      <p style="margin-top: 8px;">Cruce de Ventas con Costos de Inventario</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Identificar con que productos y laboratorios ganas mas dinero real (Utilidad).</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Como se calcula:</strong> El sistema suma el ingreso real vendido por producto y le resta el costo estimado desde Inventario: <code>Ingreso real - (Precio Compra * Cantidad)</code>.</li>
        <li><strong>Margen Global:</strong> Es el porcentaje de ganancia promedio de todo el negocio. <code>(Utilidad Total / Ingreso Total) * 100</code>.</li>
        <li><strong>Alerta Bajo Margen:</strong> Muestra productos con margen menor al 5% y alta rotacion por unidades vendidas.</li>
      </ul>
    </ModuleInfo>


    <div v-if="store.status.ventas && store.status.inventario" class="filters-bar" style="margin-bottom: 16px;">
      <div class="filter-group">
        <label>Fecha Inicio</label>
        <input
          type="date"
          v-model="filters.fecha_ini"
          :min="minAllowedDate"
          :max="todayIso"
          @change="applyFilters"
        />
      </div>
      <div class="filter-group">
        <label>Fecha Fin</label>
        <input
          type="date"
          v-model="filters.fecha_fin"
          :min="minAllowedDate"
          :max="todayIso"
          @change="applyFilters"
        />
      </div>
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 8" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom: 12px;">
        <KpiCard :icon="Gem" label="Utilidad Total" :value="store.fmt(data.kpis.utilidad_total)" />
        <KpiCard :icon="TrendingUp" label="Ingreso Cruzado" :value="store.fmt(data.kpis.ingreso_total)" />
        <KpiCard :icon="Percent" label="Margen Global" :value="data.kpis.margen_global + '%'" />
        <KpiCard :icon="Package" label="Productos Analizados" :value="store.fmtN(data.kpis.productos)" />
      </div>
      <div class="kpi-grid kpi-grid-4">
        <KpiCard :icon="AlertCircle" label="Alertas Bajo Margen" :value="store.fmtN(data.kpis.bajo_margen_count)" />
        <KpiCard :icon="Percent" label="Umbral Critico" :value="data.kpis.bajo_margen_umbral_pct + '%'" />
        <KpiCard :icon="Zap" label="Min. Alta Rotacion (uds)" :value="store.fmtN(Math.round(data.kpis.alta_rotacion_min_unidades))" />
        <KpiCard :icon="Clock" label="Dias del Periodo" :value="store.fmtN(data.kpis.dias_periodo)" />
      </div>
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><BarChart2 size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Necesitas subir <strong>Ventas</strong> e <strong>Inventario</strong> con columna <code>Precio Compra</code> para ver este analisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <div class="card">
        <SectionTitle :icon="Trophy" title="Top 15 Mas Rentables (Utilidad)" />
        <BarChart
          v-if="topRentCat.length"
          :horizontal="true"
          formatTooltip="currency"
          :categories="topRentCat"
          :series="[{ name: 'Utilidad', data: topRentData }]"
        />
      </div>

      <div class="card">
        <div class="section-header-row">
          <SectionTitle :icon="AlertTriangle" title="Alerta: Bajo Margen (<5% y alta rotacion)" />
          <button class="export-btn" @click="exportBajoMargen" v-if="data.bajo_margen.length">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
        <p class="cmd-period" style="margin: -4px 0 12px;">
          {{ store.fmtN(data.kpis.bajo_margen_count) }} alertas. Alta rotacion: >= {{ store.fmtN(data.kpis.alta_rotacion_min_unidades) }} uds vendidas en {{ data.kpis.dias_periodo }} dias.
        </p>
        <table class="data-table" v-if="data.bajo_margen.length">
          <thead>
            <tr>
              <th @click="sortByMargen('nombre')" style="cursor: pointer;">
                Producto <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('nombre') }}</span>
              </th>
              <th @click="sortByMargen('cant_vend')" style="cursor: pointer;">
                Cant <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('cant_vend') }}</span>
              </th>
              <th @click="sortByMargen('rotacion_diaria')" style="cursor: pointer;">
                Rot/dia <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('rotacion_diaria') }}</span>
              </th>
              <th @click="sortByMargen('precio_venta')" style="cursor: pointer;">
                Venta prom. <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('precio_venta') }}</span>
              </th>
              <th @click="sortByMargen('precio_compra')" style="cursor: pointer;">
                Compra <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('precio_compra') }}</span>
              </th>
              <th @click="sortByMargen('utilidad_unit')" style="cursor: pointer;">
                Util/unit <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('utilidad_unit') }}</span>
              </th>
              <th @click="sortByMargen('margen_pct')" style="cursor: pointer;">
                Margen <span style="opacity: 0.5; font-size: 10px;">{{ sortMarker('margen_pct') }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in paginatedBajoMargen" :key="row.Referencia">
              <td>{{ row.nombre }}</td>
              <td>{{ store.fmtN(row.cant_vend) }}</td>
              <td>{{ Number(row.rotacion_diaria || 0).toFixed(2) }}</td>
              <td>{{ store.fmt(row.precio_venta) }}</td>
              <td>{{ store.fmt(row.precio_compra) }}</td>
              <td>{{ store.fmt(row.utilidad_unit) }}</td>
              <td><span class="badge badge-red">{{ row.margen_pct }}%</span></td>
            </tr>
          </tbody>
        </table>
        <Paginator
          v-if="data.bajo_margen.length"
          v-model="pageBajoMargen"
          :totalItems="sortedBajoMargen.length"
          :itemsPerPage="itemsPerPage"
        />
        <p v-else style="padding: 10px; color: var(--fg-muted)">No hay productos que cumplan margen menor al 5% y alta rotacion.</p>
      </div>
    </div>

    <div v-if="data && data.matriz_abc?.length" class="card" style="margin-top: 16px;">
      <div class="section-header-row">
        <SectionTitle :icon="Crosshair" title="Matriz Estrategica: ABC Cruzado (Ventas vs Utilidad)" />
        <div style="display: flex; gap: 8px;">
          <select v-model="filtroMatriz" style="padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border); font-size: 13px;">
            <option value="Todos">Todas las clasificaciones</option>
            <option value="A-A">Tiradores (A-A) - Alta Venta, Alto Margen</option>
            <option value="A-C">Destructores (A-C) - Alta Venta, Bajo Margen</option>
            <option value="C-A">Oportunidades (C-A) - Baja Venta, Alto Margen</option>
          </select>
          <button class="export-btn" @click="exportMatriz">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Producto</th>
            <th>Ingreso (Ventas)</th>
            <th>Utilidad (Margen)</th>
            <th>Clasificacion</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in paginatedMatriz" :key="row.Referencia">
            <td>{{ row.nombre }}</td>
            <td>{{ store.fmt(row.ingreso_total) }} <span class="badge" style="margin-left: 6px;" :class="row.abc_ventas === 'A' ? 'badge-green' : 'badge-amber'">Ventas: {{ row.abc_ventas }}</span></td>
            <td>{{ store.fmt(row.utilidad_total) }} <span class="badge" style="margin-left: 6px;" :class="row.abc_margen === 'A' ? 'badge-green' : 'badge-amber'">Margen: {{ row.abc_margen }}</span></td>
            <td><strong style="font-size: 16px;">{{ row.matriz_abc }}</strong></td>
            <td>
              <span v-if="row.matriz_abc === 'A-A'" class="badge badge-green"><Rocket size="12" style="margin-right:4px;" /> Tirador</span>
              <span v-else-if="row.matriz_abc === 'A-C'" class="badge badge-red"><AlertOctagon size="12" style="margin-right:4px;" /> Destructor</span>
              <span v-else-if="row.matriz_abc === 'C-A'" class="badge badge-amber"><Lightbulb size="12" style="margin-right:4px;" /> Oportunidad</span>
              <span v-else class="badge" style="background: var(--code-bg);">Normal</span>
            </td>
          </tr>
        </tbody>
      </table>
      <Paginator
        v-model="pageMatriz"
        :totalItems="filteredMatriz.length"
        :itemsPerPage="itemsPerPage"
      />
    </div>

    <div v-if="data && data.por_laboratorio.length" class="card" style="margin-top: 16px;">
      <SectionTitle :icon="Building2" title="Rentabilidad por Laboratorio" />
      <BarChart :horizontal="true" formatTooltip="currency" :categories="topLabCat" :series="[{ name: 'Utilidad', data: topLabData }]" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import BarChart from '../components/charts/BarChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import Paginator from '../components/ui/Paginator.vue'
import { exportToCSV } from '../utils/export'
import {
  DollarSign,
  Gem,
  TrendingUp,
  Percent,
  Package,
  BarChart2,
  Trophy,
  AlertTriangle,
  AlertCircle,
  Building2,
  Download,
  Crosshair,
  Rocket,
  AlertOctagon,
  Lightbulb,
  Zap,
  Clock,
} from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.rentabilidad)
const loading = computed(() => store.loading.rentabilidad)

const filters = ref({ fecha_ini: '', fecha_fin: '' })
const minAllowedDate = '2024-01-01'
const todayIso = toIsoDate(new Date())

function toIsoDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function parseIsoDate(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [y, m, d] = value.split('-').map(Number)
  const parsed = new Date(y, m - 1, d)
  if (
    parsed.getFullYear() !== y ||
    parsed.getMonth() !== m - 1 ||
    parsed.getDate() !== d
  ) return null
  return parsed
}

function buildDateParams() {
  const params = {}
  const minDate = parseIsoDate(minAllowedDate)
  const today = parseIsoDate(todayIso)
  const start = parseIsoDate(filters.value.fecha_ini)
  const end = parseIsoDate(filters.value.fecha_fin)

  if (filters.value.fecha_ini && (!start || start < minDate || start > today)) return null
  if (filters.value.fecha_fin && (!end || end < minDate || end > today)) return null
  if (start && end && start > end) return null

  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  return params
}

function applyFilters() {
  const params = buildDateParams()
  if (!params) return
  store.fetchRentabilidad(params)
}

onMounted(() => {
  if (store.status.ventas && store.status.inventario && !data.value) {
    applyFilters()
  }
})

const sortMargenCol = ref('margen_pct')
const sortMargenDesc = ref(false)
function sortByMargen(col) {
  if (sortMargenCol.value === col) sortMargenDesc.value = !sortMargenDesc.value
  else {
    sortMargenCol.value = col
    sortMargenDesc.value = false
  }
}

function sortMarker(col) {
  if (sortMargenCol.value !== col) return '↕'
  return sortMargenDesc.value ? '▼' : '▲'
}

const sortedBajoMargen = computed(() => {
  const list = data.value?.bajo_margen ? [...data.value.bajo_margen] : []
  if (sortMargenCol.value) {
    list.sort((a, b) => {
      let valA = a[sortMargenCol.value]
      let valB = b[sortMargenCol.value]
      if (typeof valA === 'string') valA = valA.toLowerCase()
      if (typeof valB === 'string') valB = valB.toLowerCase()
      if (valA < valB) return sortMargenDesc.value ? 1 : -1
      if (valA > valB) return sortMargenDesc.value ? -1 : 1
      return 0
    })
  }
  return list
})

const topRentCat = computed(() => data.value?.top_rentables?.map(d => d.nombre) || [])
const topRentData = computed(() => data.value?.top_rentables?.map(d => d.utilidad_total) || [])

const topLabCat = computed(() => data.value?.por_laboratorio?.map(d => d.lab) || [])
const topLabData = computed(() => data.value?.por_laboratorio?.map(d => d.utilidad_total) || [])

const itemsPerPage = 10
const pageBajoMargen = ref(1)
const pageMatriz = ref(1)
const filtroMatriz = ref('Todos')

const paginatedBajoMargen = computed(() => {
  const start = (pageBajoMargen.value - 1) * itemsPerPage
  return sortedBajoMargen.value.slice(start, start + itemsPerPage)
})

const filteredMatriz = computed(() => {
  if (!data.value?.matriz_abc) return []
  let list = data.value.matriz_abc
  if (filtroMatriz.value !== 'Todos') {
    list = list.filter(r => r.matriz_abc === filtroMatriz.value)
  }
  return list
})

const paginatedMatriz = computed(() => {
  const start = (pageMatriz.value - 1) * itemsPerPage
  return filteredMatriz.value.slice(start, start + itemsPerPage)
})

watch(filtroMatriz, () => {
  pageMatriz.value = 1
})

function exportBajoMargen() {
  const cols = [
    { key: 'nombre', label: 'Producto' },
    { key: 'cant_vend', label: 'Cantidad Vendida' },
    { key: 'rotacion_diaria', label: 'Rotacion Diaria' },
    { key: 'precio_venta', label: 'Precio Promedio Venta' },
    { key: 'precio_compra', label: 'Precio Compra' },
    { key: 'utilidad_unit', label: 'Utilidad Unitaria' },
    { key: 'margen_pct', label: 'Margen (%)' },
  ]
  exportToCSV(sortedBajoMargen.value, cols, 'Alerta_Bajo_Margen')
}

function exportMatriz() {
  const cols = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'nombre', label: 'Producto' },
    { key: 'cant_vend', label: 'Cantidad Vendida' },
    { key: 'ingreso_total', label: 'Ingreso Total (Ventas)' },
    { key: 'utilidad_total', label: 'Utilidad Total (Margen)' },
    { key: 'margen_pct', label: 'Margen (%)' },
    { key: 'abc_ventas', label: 'ABC Ventas' },
    { key: 'abc_margen', label: 'ABC Margen' },
    { key: 'matriz_abc', label: 'Matriz Cruzada' },
  ]
  exportToCSV(filteredMatriz.value, cols, 'Matriz_Estrategica_ABC')
}
</script>
