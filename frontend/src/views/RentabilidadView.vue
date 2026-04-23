<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <DollarSign size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Rentabilidad y Márgenes</h2>
      </div>
      <p style="margin-top: 8px;">Cruce de Ventas con Costos de Inventario</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Identificar con qué productos y laboratorios ganas más dinero real (Utilidad).</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>¿Cómo se calcula?:</strong> El sistema toma cada venta y busca ese producto en tu archivo de Inventario. Toma el "Precio Venta" y le resta el "Precio Compra" para obtener la Utilidad Bruta Unitaria.</li>
        <li><strong>Margen Global:</strong> Es el porcentaje de ganancia promedio de todo el negocio. `(Utilidad Total / Ingreso Total) * 100`.</li>
        <li><strong>Alerta Bajo Margen:</strong> Te muestra productos que se están vendiendo mucho (alta rotación) pero que te dejan un margen de ganancia crítico (menor al 5%). ¡Cuidado con estos porque puedes estar perdiendo dinero operativo!</li>
      </ul>
    </ModuleInfo>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard :icon="Gem" label="Utilidad Total" :value="store.fmt(data.kpis.utilidad_total)" />
      <KpiCard :icon="TrendingUp" label="Ingreso Cruzado" :value="store.fmt(data.kpis.ingreso_total)" />
      <KpiCard :icon="Percent" label="Margen Global" :value="data.kpis.margen_global + '%'" />
      <KpiCard :icon="Package" label="Productos Analizados" :value="store.fmtN(data.kpis.productos)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon"><BarChart2 size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Necesitas subir **Ventas** e **Inventario** (con columna 'Precio Compra') para ver este análisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <div class="card">
        <SectionTitle :icon="Trophy" title="Top 15 Más Rentables (Utilidad)" />
        <BarChart v-if="topRentCat.length" :horizontal="true" formatTooltip="currency" :categories="topRentCat" :series="[{name: 'Utilidad', data: topRentData}]" />
      </div>

      <div class="card">
        <SectionTitle :icon="AlertTriangle" title="Alerta: Bajo Margen (<5% y alta rotación)" />
        <table class="data-table" v-if="data.bajo_margen.length">
          <thead>
            <tr>
              <th @click="sortByMargen('nombre')" style="cursor: pointer;">
                Producto <span style="opacity: 0.5; font-size: 10px;">{{ sortMargenCol === 'nombre' ? (sortMargenDesc ? '▼' : '▲') : '↕' }}</span>
              </th>
              <th @click="sortByMargen('cant_vend')" style="cursor: pointer;">
                Cant <span style="opacity: 0.5; font-size: 10px;">{{ sortMargenCol === 'cant_vend' ? (sortMargenDesc ? '▼' : '▲') : '↕' }}</span>
              </th>
              <th @click="sortByMargen('precio_venta')" style="cursor: pointer;">
                Venta <span style="opacity: 0.5; font-size: 10px;">{{ sortMargenCol === 'precio_venta' ? (sortMargenDesc ? '▼' : '▲') : '↕' }}</span>
              </th>
              <th @click="sortByMargen('margen_pct')" style="cursor: pointer;">
                Margen <span style="opacity: 0.5; font-size: 10px;">{{ sortMargenCol === 'margen_pct' ? (sortMargenDesc ? '▼' : '▲') : '↕' }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in sortedBajoMargen" :key="row.Referencia">
              <td>{{ row.nombre }}</td>
              <td>{{ row.cant_vend }}</td>
              <td>{{ store.fmt(row.precio_venta) }}</td>
              <td><span class="badge badge-red">{{ row.margen_pct }}%</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else style="padding: 10px; color: var(--fg-muted)">No hay productos en alerta.</p>
      </div>
    </div>
    
    <div v-if="data && data.por_laboratorio.length" class="card" style="margin-top: 16px;">
      <SectionTitle :icon="Building2" title="Rentabilidad por Laboratorio" />
      <BarChart :horizontal="true" formatTooltip="currency" :categories="topLabCat" :series="[{name: 'Utilidad', data: topLabData}]" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import BarChart from '../components/charts/BarChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import { DollarSign, Gem, TrendingUp, Percent, Package, BarChart2, Trophy, AlertTriangle, Building2 } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.rentabilidad)
const loading = computed(() => store.loading.rentabilidad)

onMounted(() => {
  if (store.status.ventas && store.status.inventario && !data.value) {
    store.fetchRentabilidad()
  }
})

const sortMargenCol = ref('margen_pct')
const sortMargenDesc = ref(false)
function sortByMargen(col) {
  if (sortMargenCol.value === col) sortMargenDesc.value = !sortMargenDesc.value
  else { sortMargenCol.value = col; sortMargenDesc.value = false }
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
</script>
