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
        <li><strong>Filtros Dinámicos:</strong> Puedes filtrar la información por Sede, Fecha y Categoría. El sistema agrupa los registros del archivo original basados en estos criterios.</li>
        <li><strong>Top Productos y Labs:</strong> Calcula la suma total de "Cant" (unidades) o "Ingreso" por producto y laboratorio, organizados de mayor a menor.</li>
        <li><strong>Ventas por Categoría:</strong> Agrupa todos los ingresos basándose en la columna "Nivel" (si está disponible en tu archivo), mostrándote la distribución del negocio.</li>
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
      <KpiCard icon="🏆" label="Top Producto" :value="data.top_productos[0]?.nombre || '—'" />
      <KpiCard icon="🧪" label="Top Lab" :value="data.top_labs[0]?.lab || '—'" />
      <KpiCard v-if="data.vendedores.length" icon="👨‍💼" label="Top Vendedor" :value="data.vendedores[0]?.vendedor || '—'" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon">📁</div>
      <h3>No hay datos de ventas</h3>
      <p>Sube al menos un archivo de ventas para ver este análisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Top Productos -->
      <div class="card">
        <SectionTitle icon="🏆" title="Top 15 Productos (Unidades)" />
        <BarChart v-if="topProdCat.length" :horizontal="true" :categories="topProdCat" :series="[{name: 'Unidades', data: topProdData}]" />
      </div>

      <!-- Top Labs -->
      <div class="card">
        <SectionTitle icon="🏢" title="Top 10 Laboratorios (Ingresos)" />
        <BarChart v-if="topLabCat.length" :horizontal="true" formatTooltip="currency" :categories="topLabCat" :series="[{name: 'Ingresos', data: topLabData}]" />
      </div>
    </div>

    <div v-if="data && data.por_categoria.length" class="card" style="margin-top: 16px;">
      <SectionTitle icon="📑" title="Ventas por Categoría" />
      <DonutChart :labels="catLabels" :series="catSeries" />
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import BarChart from '../components/charts/BarChart.vue'
import DonutChart from '../components/charts/DonutChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'

const store = useDashboardStore()
const data = computed(() => store.data.ventas)
const loading = computed(() => store.loading.ventas)

const filters = ref({
  sede: 'Todas',
  nivel: 'Todos',
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
</script>
