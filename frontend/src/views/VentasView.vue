<template>
  <div>
    <div class="page-header">
      <h2>📈 Análisis de Ventas</h2>
      <p>Desglose por productos, categorías y vendedores</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Entender qué se vende, quién lo vende y en qué categorías.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Filtros Dinámicos:</strong> Puedes filtrar por Sede, Fecha, Categoría y Laboratorio.</li>
        <li><strong>Top Productos y Labs:</strong> Suma total de unidades e ingresos, organizados de mayor a menor.</li>
        <li><strong>Tendencia Mensual:</strong> Evolución de ingresos mes a mes para detectar estacionalidad.</li>
        <li><strong>Tabla Detalle:</strong> Todos los productos vendidos con búsqueda para encontrar cualquier referencia.</li>
      </ul>
    </ModuleInfo>

    <!-- Filtros -->
    <div v-if="data" class="filters-bar">
      <div class="filter-group">
        <label>Sede</label>
        <select v-model="filters.sede" @change="applyFilters">
          <option value="Todas">Todas</option>
          <option v-for="s in data.filtros.sedes" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="filter-group" v-if="data.filtros.niveles.length">
        <label>Categoría (Nivel)</label>
        <select v-model="filters.nivel" @change="applyFilters">
          <option value="Todos">Todas</option>
          <option v-for="n in data.filtros.niveles" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <div class="filter-group" v-if="data.filtros.laboratorios?.length">
        <label>Laboratorio</label>
        <select v-model="filters.laboratorio" @change="applyFilters">
          <option value="Todos">Todos</option>
          <option v-for="l in data.filtros.laboratorios" :key="l" :value="l">{{ l }}</option>
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

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard icon="📄" label="Registros Filtrados" :value="store.fmtN(data.registros)" />
      <KpiCard icon="💰" label="Ingreso Total" :value="store.fmt(data.ingreso_total)" />
      <KpiCard icon="📊" label="Promedio Diario" :value="store.fmt(data.promedio_diario)" />
      <KpiCard icon="📅" label="Días del Periodo" :value="data.dias_periodo + ' días'" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon">📁</div>
      <h3>No hay datos de ventas</h3>
      <p>Sube al menos un archivo de ventas para ver este análisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <div class="card">
        <SectionTitle icon="🏆" title="Top 15 Productos (Unidades)" />
        <BarChart v-if="topProdCat.length" :horizontal="true" :categories="topProdCat" :series="[{name: 'Unidades', data: topProdData}]" />
      </div>
      <div class="card">
        <SectionTitle icon="🏢" title="Top 10 Laboratorios (Ingresos)" />
        <BarChart v-if="topLabCat.length" :horizontal="true" formatTooltip="currency" :categories="topLabCat" :series="[{name: 'Ingresos', data: topLabData}]" />
      </div>
    </div>

    <!-- Tendencia Mensual -->
    <div v-if="data && data.tendencia_mensual?.length" class="card" style="margin-top: 16px;">
      <SectionTitle icon="📈" title="Tendencia Mensual de Ingresos" />
      <LineChart :categories="tendMesCat" :series="[{name: 'Ingresos', data: tendMesData}]" />
    </div>

    <!-- Vendedores -->
    <div v-if="data && data.vendedores?.length" class="card" style="margin-top: 16px;">
      <SectionTitle icon="👨‍💼" title="Rendimiento por Vendedor" />
      <div style="max-height: 350px; overflow-y: auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Vendedor</th>
              <th>Unidades</th>
              <th>Ingresos</th>
              <th>Transacciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in data.vendedores" :key="v.vendedor">
              <td style="font-weight: 600;">{{ v.vendedor }}</td>
              <td>{{ store.fmtN(v.unidades) }}</td>
              <td>{{ store.fmt(v.ingresos) }}</td>
              <td>{{ store.fmtN(v.facturas) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="data && data.por_categoria.length" class="card" style="margin-top: 16px;">
      <SectionTitle icon="📑" title="Ventas por Categoría" />
      <DonutChart :labels="catLabels" :series="catSeries" />
    </div>

    <!-- Tabla Detalle Productos -->
    <div v-if="data && data.detalle_productos?.length" class="card" style="margin-top: 16px;">
      <SectionTitle icon="📋" title="Detalle de Productos Vendidos" />
      <input type="text" v-model="searchDetalle" placeholder="🔍 Buscar por referencia, nombre o laboratorio..."
             style="width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 12px; font-size: 14px;" />
      <div style="max-height: 400px; overflow-y: auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Referencia</th>
              <th>Descripción</th>
              <th>Laboratorio</th>
              <th>Unidades</th>
              <th>Ingreso</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredDetalle" :key="row.Referencia">
              <td>{{ row.Referencia }}</td>
              <td>{{ row.Descripcion?.substring(0, 35) }}</td>
              <td>{{ row.Laboratorio?.substring(0, 25) }}</td>
              <td>{{ store.fmtN(row.unidades) }}</td>
              <td>{{ store.fmt(row.ingreso) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style="color: var(--fg-muted); margin-top: 8px; font-size: 12px;">
        Mostrando {{ filteredDetalle.length }} de {{ data.detalle_productos.length }} productos
      </p>
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

const store = useDashboardStore()
const data = computed(() => store.data.ventas)
const loading = computed(() => store.loading.ventas)
const searchDetalle = ref('')

const filters = ref({
  sede: 'Todas',
  nivel: 'Todos',
  laboratorio: 'Todos',
  fecha_ini: '',
  fecha_fin: ''
})

function applyFilters() {
  const params = { ...filters.value }
  if (!params.fecha_ini) delete params.fecha_ini
  if (!params.fecha_fin) delete params.fecha_fin
  store.fetchVentas(params)
}

onMounted(() => {
  if (store.status.ventas && !data.value) applyFilters()
})

const topProdCat = computed(() => data.value?.top_productos?.map(d => d.nombre) || [])
const topProdData = computed(() => data.value?.top_productos?.map(d => d.Cant) || [])
const topLabCat = computed(() => data.value?.top_labs?.map(d => d.lab) || [])
const topLabData = computed(() => data.value?.top_labs?.map(d => d.Ingreso) || [])
const catLabels = computed(() => data.value?.por_categoria?.map(d => d.Nivel) || [])
const catSeries = computed(() => data.value?.por_categoria?.map(d => d.Ingreso) || [])
const tendMesCat = computed(() => data.value?.tendencia_mensual?.map(d => d.mes) || [])
const tendMesData = computed(() => data.value?.tendencia_mensual?.map(d => d.ingreso) || [])

const filteredDetalle = computed(() => {
  const list = data.value?.detalle_productos || []
  if (!searchDetalle.value) return list
  const q = searchDetalle.value.toLowerCase()
  return list.filter(r =>
    (r.Referencia || '').toString().toLowerCase().includes(q) ||
    (r.Descripcion || '').toLowerCase().includes(q) ||
    (r.Laboratorio || '').toLowerCase().includes(q)
  )
})
</script>
