<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <BrainCircuit size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Inventario Inteligente</h2>
      </div>
      <p style="margin-top: 8px;">Control de reabastecimiento por clasificación ABC y análisis de cobertura</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Cómo usar esta página?</strong> Es muy fácil: mira la tabla de abajo y compra lo que dice en la última columna.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Zona Sana (Verde):</strong> Tienes suficiente para 25 a 40 días. ¡Todo bien!</li>
        <li><strong>Bajo Stock (Rojo/Naranja):</strong> Te queda poco. Mira la columna <strong>"Cantidad a Comprar"</strong> para saber cuánto pedir.</li>
        <li><strong>Venta Diaria Esperada:</strong> Cuántas cajitas vendes en promedio cada día.</li>
        <li><strong>Días que Alcanza:</strong> Para cuántos días tienes medicina antes de quedar en cero.</li>
      </ul>
    </ModuleInfo>

    <!-- Filtros -->
    <div v-if="data" class="filters-bar">
      <div class="filter-group">
        <label>Sede / Bodega</label>
        <select v-model="sedeSeleccionada" @change="applyFilters">
          <option value="Todas">Todas (Consolidado)</option>
          <option v-for="s in data.sedes_disponibles" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Mínimo sano (días)</label>
        <input type="number" min="1" v-model.number="store.settings.inv_min_dias" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label>Máximo sano (días)</label>
        <input type="number" min="2" v-model.number="store.settings.inv_max_dias" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label>Inventario quieto (días)</label>
        <input type="number" min="1" v-model.number="store.settings.quieto_dias" @change="applyFilters" />
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

    <div v-if="store.errors.inventario" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.inventario }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard :icon="AlertTriangle" :label="'Bajo Stock (< ' + data.kpis.inv_min_dias + ' días)'" :value="store.fmtN(data.kpis.bajo_stock)" />
      <KpiCard :icon="OctagonX"     label="Agotado (0 stock, con demanda)" :value="store.fmtN(data.kpis.sin_stock)" />
      <KpiCard :icon="TrendingUp"   :label="'Sobrestock (> ' + data.kpis.inv_max_dias + ' días)'" :value="store.fmtN(data.kpis.sobre_stock || 0)" />
      <KpiCard :icon="Snail"        :label="'Sin Rotación (> ' + data.kpis.quieto_dias + ' días)'" :value="store.fmtN(data.kpis.inventario_quieto)" />
      <KpiCard :icon="Banknote"     :label="'Capital Quieto (> ' + data.kpis.quieto_dias + 'd)'" :value="store.fmt(data.kpis.capital_quieto)" />
      <KpiCard :icon="Banknote"     :label="'Capital en Exceso (> ' + data.kpis.inv_max_dias + 'd)'" :value="store.fmt(data.kpis.capital_exceso || 0)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><PackageOpen size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Sube el archivo de <strong>Inventario</strong> y <strong>Ventas</strong> para calcular la rotación cruzada.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Tabla de Bajo Stock -->
      <div class="card" style="grid-column: span 2;">
        <div class="section-header-row">
          <SectionTitle :icon="ClipboardList" :title="'Reabastecer — Bajo Mínimo (' + (data.kpis.inv_min_dias || 25) + ' días) con Demanda Activa'" />
          <button class="export-btn" @click="exportBajoStock">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
        <div>
          <table class="data-table">
            <thead>
              <tr>
                <th @click="sortByBajo('clasificacion_abc')" style="cursor: pointer;">
                  Clase <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'clasificacion_abc' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByBajo('Referencia')" style="cursor: pointer;">
                  Referencia <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'Referencia' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByBajo('Descripcion')" style="cursor: pointer;">
                  Descripción <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'Descripcion' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByBajo('rotacion_proyectada')" style="cursor: pointer;">
                  Venta Diaria Esperada <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'rotacion_proyectada' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByBajo('Total')" style="cursor: pointer;">
                  Inventario Actual <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'Total' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByBajo('cobertura_dias')" style="cursor: pointer;">
                  Días que Alcanza <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'cobertura_dias' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByBajo('deficit')" style="cursor: pointer;">
                  Cantidad a Comprar <span style="opacity: 0.5; font-size: 10px;">{{ sortBajoCol === 'deficit' ? (sortBajoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in paginatedBajo" :key="row.Referencia">
                <td style="text-align: center;">
                  <span class="badge" 
                        :class="{'badge-green': row.clasificacion_abc === 'A', 'badge-amber': row.clasificacion_abc === 'B', 'badge-red': row.clasificacion_abc === 'C'}">
                    {{ row.clasificacion_abc }}
                  </span>
                </td>
                <td>{{ row.Referencia }}</td>
                <td>{{ row.Descripcion?.substring(0, 35) }}</td>
                <td>
                  {{ row.rotacion_proyectada > 0 ? row.rotacion_proyectada.toFixed(2) : '0.00' }} uds/día
                  <span v-if="row.factor_tendencia > 1.2" class="badge badge-amber" style="margin-left: 4px; font-size: 10px; padding: 2px 4px;" title="Demanda Acelerando"><TrendingUp size="12" /></span>
                  <span v-else-if="row.factor_tendencia < 0.8" class="badge" style="margin-left: 4px; font-size: 10px; padding: 2px 4px; background: var(--border);" title="Demanda Cayendo"><TrendingDown size="12" /></span>
                </td>
                <td><span class="badge" :class="row.Total === 0 ? 'badge-red' : 'badge-amber'">{{ store.fmtN(row.Total) }}</span></td>
                <td>
                  <span class="badge" 
                    :class="row.cobertura_dias === 0 ? 'badge-red' : row.cobertura_dias < data.kpis.inv_min_dias * 0.4 ? 'badge-red' : row.cobertura_dias < data.kpis.inv_min_dias ? 'badge-amber' : 'badge-green'">
                    {{ row.cobertura_dias < 9999 ? Math.round(row.cobertura_dias) + ' d' : '+999 d' }}
                  </span>
                </td>
                <td><span style="color: var(--accent); font-weight: 700;">{{ store.fmtN(row.deficit) }} uds</span></td>
              </tr>
              <tr v-if="!data.bajo_stock_tabla.length">
                <td colspan="7" style="text-align: center; color: var(--fg-muted);">No hay alertas urgentes de reabastecimiento.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Paginator 
          v-model="pageBajo" 
          :totalItems="sortedBajo.length" 
          :itemsPerPage="itemsPerPage" 
        />
      </div>

      <!-- Top Déficit -->
      <div class="card">
        <SectionTitle :icon="TrendingDown" title="Top 15 Productos para Pedir Ya (Unidades)" />
        <BarChart v-if="topDefCat.length" :horizontal="true" :categories="topDefCat" :series="[{name: 'Déficit', data: topDefData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay productos con déficit urgente.</p>
      </div>
      
      <!-- Top Capital Inmovilizado -->
      <div class="card">
        <SectionTitle :icon="Landmark" title="Top 15 Mayor Capital Inmovilizado" />
        <BarChart v-if="topQuietoCat.length" :horizontal="true" formatTooltip="currency" :categories="topQuietoCat" :series="[{name: 'Capital Inmovilizado', data: topQuietoData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay capital inmovilizado destacable.</p>
      </div>
    </div>

    <div v-if="data" class="grid-2" style="margin-top: 16px;">
      <!-- Tabla de Inventario Quieto -->
      <div class="card" style="grid-column: span 2;">
        <div class="section-header-row">
          <SectionTitle :icon="Snail" :title="'Inventario Quieto (Sin Ventas > ' + data.kpis.quieto_dias + ' días)'" />
          <button class="export-btn" @click="exportQuieto">
            <Download size="16" /> Exportar CSV
          </button>
        </div>
        <div>
          <table class="data-table">
            <thead>
              <tr>
                <th @click="sortByQuieto('Referencia')" style="cursor: pointer;">
                  Referencia <span style="opacity: 0.5; font-size: 10px;">{{ sortQuietoCol === 'Referencia' ? (sortQuietoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByQuieto('Descripcion')" style="cursor: pointer;">
                  Descripción <span style="opacity: 0.5; font-size: 10px;">{{ sortQuietoCol === 'Descripcion' ? (sortQuietoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByQuieto('dias_sin_venta')" style="cursor: pointer;">
                  Días Sin Venta <span style="opacity: 0.5; font-size: 10px;">{{ sortQuietoCol === 'dias_sin_venta' ? (sortQuietoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByQuieto('Total')" style="cursor: pointer;">
                  Stock <span style="opacity: 0.5; font-size: 10px;">{{ sortQuietoCol === 'Total' ? (sortQuietoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
                <th @click="sortByQuieto('capital_inmovilizado')" style="cursor: pointer;">
                  Capital Atrapado <span style="opacity: 0.5; font-size: 10px;">{{ sortQuietoCol === 'capital_inmovilizado' ? (sortQuietoDesc ? '▼' : '▲') : '↕' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in paginatedQuieto" :key="row.Referencia">
                <td>{{ row.Referencia }}</td>
                <td>{{ row.Descripcion?.substring(0, 45) }}</td>
                <td><span class="badge badge-red">{{ row.dias_sin_venta >= 9999 ? 'NUNCA' : row.dias_sin_venta + ' d' }}</span></td>
                <td>{{ store.fmtN(row.Total) }}</td>
                <td style="font-weight: 600;">{{ store.fmt(row.capital_inmovilizado) }}</td>
              </tr>
              <tr v-if="!data.inventario_quieto_tabla.length">
                <td colspan="5" style="text-align: center; color: var(--fg-muted);">¡Excelente! Todo el inventario está rotando.</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Paginator 
          v-model="pageQuieto" 
          :totalItems="sortedQuieto.length" 
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
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import Paginator from '../components/ui/Paginator.vue'
import { exportToCSV } from '../utils/export'
import { BrainCircuit, AlertTriangle, OctagonX, Snail, Banknote, PackageOpen, ClipboardList, TrendingDown, Landmark, Download, TrendingUp } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.inventario)
const loading = computed(() => store.loading.inventario)

const sedeSeleccionada = ref('Todas')
const filters = ref({ fecha_ini: '', fecha_fin: '' })

function applyFilters() {
  const params = { sede: sedeSeleccionada.value }
  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  store.fetchInventario(params)
}

onMounted(() => {
  if (store.status.inventario && !data.value) {
    applyFilters()
  }
})

const sortBajoCol = ref('clasificacion_abc')
const sortBajoDesc = ref(false)
function sortByBajo(col) {
  if (sortBajoCol.value === col) sortBajoDesc.value = !sortBajoDesc.value
  else { sortBajoCol.value = col; sortBajoDesc.value = false }
}

const sortedBajo = computed(() => {
  const list = data.value?.bajo_stock_tabla ? [...data.value.bajo_stock_tabla] : []
  if (sortBajoCol.value) {
    list.sort((a, b) => {
      let valA = a[sortBajoCol.value]
      let valB = b[sortBajoCol.value]
      if (typeof valA === 'string') valA = valA.toLowerCase()
      if (typeof valB === 'string') valB = valB.toLowerCase()
      if (valA < valB) return sortBajoDesc.value ? 1 : -1
      if (valA > valB) return sortBajoDesc.value ? -1 : 1
      return 0
    })
  }
  return list
})

const sortQuietoCol = ref('capital_inmovilizado')
const sortQuietoDesc = ref(true)
function sortByQuieto(col) {
  if (sortQuietoCol.value === col) sortQuietoDesc.value = !sortQuietoDesc.value
  else { sortQuietoCol.value = col; sortQuietoDesc.value = true }
}

const sortedQuieto = computed(() => {
  const list = data.value?.inventario_quieto_tabla ? [...data.value.inventario_quieto_tabla] : []
  if (sortQuietoCol.value) {
    list.sort((a, b) => {
      let valA = a[sortQuietoCol.value]
      let valB = b[sortQuietoCol.value]
      if (typeof valA === 'string') valA = valA.toLowerCase()
      if (typeof valB === 'string') valB = valB.toLowerCase()
      if (valA < valB) return sortQuietoDesc.value ? 1 : -1
      if (valA > valB) return sortQuietoDesc.value ? -1 : 1
      return 0
    })
  }
  return list
})

const topDefCat = computed(() => data.value?.top_deficit?.map(d => d.nombre) || [])
const topDefData = computed(() => data.value?.top_deficit?.map(d => d.deficit) || [])

const topQuietoCat = computed(() => data.value?.top_quieto?.map(d => d.nombre) || [])
const topQuietoData = computed(() => data.value?.top_quieto?.map(d => d.capital_inmovilizado) || [])

// Paginación
const itemsPerPage = 10
const pageBajo = ref(1)
const pageQuieto = ref(1)

const paginatedBajo = computed(() => {
  const start = (pageBajo.value - 1) * itemsPerPage
  return sortedBajo.value.slice(start, start + itemsPerPage)
})

const paginatedQuieto = computed(() => {
  const start = (pageQuieto.value - 1) * itemsPerPage
  return sortedQuieto.value.slice(start, start + itemsPerPage)
})

// Exportación
function exportBajoStock() {
  const cols = [
    { key: 'clasificacion_abc', label: 'Importancia (ABC)' },
    { key: 'Referencia', label: 'Código' },
    { key: 'Descripcion', label: 'Nombre del Producto' },
    { key: 'rotacion_diaria', label: 'Venta Diaria Promedio', formatter: v => v ? Number(v).toFixed(2) : 0 },
    { key: 'rotacion_proyectada', label: 'Venta Diaria Esperada (Tendencia)', formatter: v => v ? Number(v).toFixed(2) : 0 },
    { key: 'Total', label: 'Inventario Actual' },
    { key: 'cobertura_dias', label: 'Días que alcanza el stock', formatter: v => v && v < 9999 ? Number(v).toFixed(1) : '+999' },
    { key: 'deficit', label: 'Unidades a Comprar' }
  ]
  exportToCSV(sortedBajo.value, cols, 'Alerta_Bajo_Stock')
}

function exportQuieto() {
  const cols = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Descripción' },
    { key: 'dias_sin_venta', label: 'Días Sin Venta' },
    { key: 'Total', label: 'Stock Actual' },
    { key: 'capital_inmovilizado', label: 'Capital Inmovilizado', formatter: v => v ? Math.round(v) : 0 }
  ]
  exportToCSV(sortedQuieto.value, cols, 'Inventario_Quieto')
}
</script>
