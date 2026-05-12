<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <Scale size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Conciliación y Cobertura (Compras vs Ventas)</h2>
      </div>
      <p style="margin-top: 8px;">Cálculo de Inventario Inicial por ingeniería inversa y días de cobertura de stock</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Reconstruir el historial exacto de tu inventario y predecir cuándo te quedarás sin stock.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Ingeniería Inversa (Inv. Inicial):</strong> <code>Inventario Inicial = Actual + Vendido - Comprado</code></li>
        <li><strong>Cobertura (Días):</strong> Para cuántos días alcanza el inventario actual al ritmo actual de venta.</li>
        <li><strong>Filtros:</strong> Filtra por proveedor, estado (sobrecompra/desabastecimiento) o busca por nombre/referencia.</li>
      </ul>
    </ModuleInfo>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard :icon="ShoppingCart" label="Total Comprado (Uds)" :value="store.fmtN(data.kpis.total_comprado)" />
      <KpiCard :icon="Package" label="Total Vendido (Uds)" :value="store.fmtN(data.kpis.total_vendido)" />
      <KpiCard :icon="AlertTriangle" label="Items Sobrecomprados" :value="store.fmtN(data.kpis.n_sobre_compra)" />
      <KpiCard :icon="Timer" label="Días del Periodo" :value="data.kpis.dias_periodo + ' días'" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><Scale size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Sube archivos de <strong>Inventario, Compras y Ventas</strong> para ejecutar la conciliación matemática.</p>
    </div>

    <!-- Filtros -->
    <div v-if="data" class="filters-bar">
      <div class="filter-group">
        <label>Proveedor</label>
        <select v-model="filters.proveedor" @change="applyFilters">
          <option value="Todos">Todos</option>
          <option v-for="p in data.filtros?.proveedores" :key="p" :value="p">{{ p.substring(0, 40) }}</option>
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
      <div class="filter-group">
        <label>Estado</label>
        <select v-model="filters.estado" @change="applyFilters">
          <option value="Todos">Todos</option>
          <option value="sobre_compra">Sobrecompra</option>
          <option value="desabastecimiento">Desabastecimiento</option>
          <option value="equilibrio">Equilibrio</option>
        </select>
      </div>
      <div class="filter-group" style="flex: 2;">
        <label>Buscar</label>
        <input type="text" v-model="filters.buscar" @input="debouncedSearch" placeholder="🔍 Referencia o nombre..." 
               style="padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; width: 100%;" />
      </div>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Conciliación Matemática -->
      <div class="card" style="grid-column: span 2;">
        <div class="section-header-row">
          <SectionTitle :icon="Calculator" :title="'Flujo de Inventario (' + (data.comparativo?.length || 0) + ' productos)'" />
          <button class="export-btn" @click="exportComparativo">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
        <div>
          <table class="data-table">
            <thead>
              <tr>
                <th @click="sortByComp('Referencia')" style="cursor: pointer;">
                  Referencia <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'Referencia' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('Descripcion')" style="cursor: pointer;">
                  Descripción <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'Descripcion' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('inv_inicial')" style="cursor: pointer; background: var(--bg); border-left: 1px solid var(--border);">
                  Inv. Inicial <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'inv_inicial' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('uds_compradas')" style="cursor: pointer; color: var(--green);">
                  + Comprado <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'uds_compradas' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('uds_vendidas')" style="cursor: pointer; color: var(--red);">
                  - Vendido <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'uds_vendidas' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('inv_actual')" style="cursor: pointer; background: var(--bg); border-right: 1px solid var(--border); font-weight: 700;">
                  = Inv. Actual <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'inv_actual' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('cobertura_dias')" style="cursor: pointer;">
                  Cobertura <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'cobertura_dias' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByComp('estado')" style="cursor: pointer;">
                  Estado <span style="opacity: 0.5; font-size: 10px;">{{ sortCompCol === 'estado' ? (sortCompDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in paginatedComparativo" :key="row.Referencia">
                <td>{{ row.Referencia }}</td>
                <td>{{ row.Descripcion?.substring(0, 30) || 'N/A' }}</td>
                <td style="background: var(--bg); border-left: 1px solid var(--border);">{{ store.fmtN(row.inv_inicial) }}</td>
                <td style="color: var(--green);">{{ store.fmtN(row.uds_compradas) }}</td>
                <td style="color: var(--red);">{{ store.fmtN(row.uds_vendidas) }}</td>
                <td style="background: var(--bg); border-right: 1px solid var(--border); font-weight: 700;">{{ store.fmtN(row.inv_actual) }}</td>
                <td>
                  <span class="badge" 
                        :class="row.cobertura_dias < data.kpis.inv_min_dias ? 'badge-red' : ((row.cobertura_dias >= 180 && isPerecedero(row)) ? 'badge-red' : (row.cobertura_dias > data.kpis.inv_max_dias ? 'badge-amber' : 'badge-green'))">
                    <template v-if="row.cobertura_dias >= 9999">
                      {{ isPerecedero(row) ? '+999 d (Riesgo Vencimiento)' : '+999 d (No perecedero)' }}
                    </template>
                    <template v-else>
                      {{ Math.round(row.cobertura_dias) }} d
                      <span v-if="row.cobertura_dias >= 180">
                        {{ isPerecedero(row) ? ' (Riesgo Vencimiento)' : ' (No perecedero)' }}
                      </span>
                    </template>
                  </span>
                </td>
                <td>
                  <span class="badge" style="display: inline-flex; align-items: center; gap: 4px;" :class="{'badge-amber': row.estado === 'sobre_compra', 'badge-red': row.estado === 'desabastecimiento', 'badge-green': row.estado === 'equilibrio'}">
                    <ArrowUpCircle v-if="row.estado === 'sobre_compra'" size="14" />
                    <AlertCircle v-else-if="row.estado === 'desabastecimiento'" size="14" />
                    <CheckCircle2 v-else size="14" />
                    {{ row.estado === 'sobre_compra' ? 'Sobre' : (row.estado === 'desabastecimiento' ? 'Falta' : 'OK') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Paginator 
          v-model="pageComparativo" 
          :totalItems="sortedComparativo.length" 
          :itemsPerPage="itemsPerPage" 
        />
      </div>

      <!-- Top Proveedores -->
      <div class="card" style="grid-column: span 2;">
        <SectionTitle :icon="Truck" title="Top 10 Proveedores (Unidades Compradas)" />
        <BarChart v-if="topProvCat.length" :horizontal="true" :categories="topProvCat" :series="[{name: 'Unidades', data: topProvData}]" />
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
import Paginator from '../components/ui/Paginator.vue'
import { exportToCSV } from '../utils/export'
import { Scale, ShoppingCart, Package, AlertTriangle, Timer, Calculator, Truck, Download, ArrowUpCircle, AlertCircle, CheckCircle2 } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.compras)
const loading = computed(() => store.loading.compras)

const filters = ref({
  proveedor: 'Todos',
  estado: 'Todos',
  fecha_ini: '',
  fecha_fin: '',
  buscar: ''
})

let debounceTimer = null
function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => applyFilters(), 400)
}

function applyFilters() {
  store.fetchCompras(filters.value)
}

const sortCompCol = ref('inv_actual')
const sortCompDesc = ref(true)
function sortByComp(col) {
  if (sortCompCol.value === col) sortCompDesc.value = !sortCompDesc.value
  else { sortCompCol.value = col; sortCompDesc.value = true }
}

const sortedComparativo = computed(() => {
  const list = data.value?.comparativo ? [...data.value.comparativo] : []
  if (sortCompCol.value) {
    list.sort((a, b) => {
      let valA = a[sortCompCol.value]
      let valB = b[sortCompCol.value]
      if (typeof valA === 'string') valA = valA.toLowerCase()
      if (typeof valB === 'string') valB = valB.toLowerCase()
      if (valA < valB) return sortCompDesc.value ? 1 : -1
      if (valA > valB) return sortCompDesc.value ? -1 : 1
      return 0
    })
  }
  return list
})

onMounted(() => {
  if (store.status.ventas && store.status.compras && store.status.inventario && !data.value) {
    applyFilters()
  }
})

function isPerecedero(row) {
  const textToCheck = ((row.Nivel || '') + ' ' + (row.Descripcion || '')).toLowerCase()
  const noPerecederos = [
    'silla', 'equipo', 'mueble', 'material', 'insumo', 'dispositivo', 'dotacion', 
    'accesorio', 'ortopedico', 'camilla', 'caneca', 'papeleria', 'aseo', 'ferula', 
    'inmovilizador', 'termometro', 'tensiometro', 'fonendoscopio', 'muleta', 
    'baston', 'caminador', 'cabestrillo', 'faja', 'rodillera', 'tobillera', 
    'muñequera', 'collarin', 'nebulizador', 'glucometro', 'lanceta', 'tira reactiva',
    'algodon', 'jeringa', 'aguja', 'guante', 'tapaboca', 'mascarilla', 'bata', 'gorro', 'polaina'
  ]
  return !noPerecederos.some(kw => textToCheck.includes(kw))
}

const topProvCat = computed(() => data.value?.top_proveedores?.map(d => d.proveedor) || [])
const topProvData = computed(() => data.value?.top_proveedores?.map(d => d.unidades) || [])

// Paginación
const itemsPerPage = 10
const pageComparativo = ref(1)

const paginatedComparativo = computed(() => {
  const start = (pageComparativo.value - 1) * itemsPerPage
  return sortedComparativo.value.slice(start, start + itemsPerPage)
})

// Exportación
function exportComparativo() {
  const cols = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Descripción' },
    { key: 'inv_inicial', label: 'Inv. Inicial' },
    { key: 'uds_compradas', label: '+ Comprado' },
    { key: 'uds_vendidas', label: '- Vendido' },
    { key: 'inv_actual', label: '= Inv. Actual' },
    { key: 'cobertura_dias', label: 'Días Cobertura' },
    { key: 'estado', label: 'Estado' }
  ]
  exportToCSV(sortedComparativo.value, cols, 'Conciliacion_Inventario')
}
</script>
