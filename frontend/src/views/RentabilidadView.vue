<template>
  <div>
    <div class="page-header">
      <h2>💰 Rentabilidad y Márgenes</h2>
      <p>Cruce de Ventas con Costos de Inventario</p>
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
      <KpiCard icon="💎" label="Utilidad Total" :value="store.fmt(data.kpis.utilidad_total)" />
      <KpiCard icon="📈" label="Ingreso Cruzado" :value="store.fmt(data.kpis.ingreso_total)" />
      <KpiCard icon="🏷️" label="Margen Global" :value="data.kpis.margen_global + '%'" />
      <KpiCard icon="📦" label="Productos Analizados" :value="store.fmtN(data.kpis.productos)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon">📊</div>
      <h3>Faltan datos</h3>
      <p>Necesitas subir **Ventas** e **Inventario** (con columna 'Precio Compra') para ver este análisis.</p>
    </div>

    <div v-if="data" class="grid-2">
      <div class="card">
        <SectionTitle icon="🏆" title="Top 15 Más Rentables (Utilidad)" />
        <BarChart v-if="topRentCat.length" :horizontal="true" formatTooltip="currency" :categories="topRentCat" :series="[{name: 'Utilidad', data: topRentData}]" />
      </div>

      <div class="card">
        <SectionTitle icon="⚠️" title="Alerta: Bajo Margen (<5% y alta rotación)" />
        <table class="data-table" v-if="data.bajo_margen.length">
          <thead>
            <tr>
              <th>Producto</th>
              <th>Cant</th>
              <th>Venta</th>
              <th>Margen</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.bajo_margen" :key="row.Referencia">
              <td>{{ row.nombre }}</td>
              <td>{{ row.cant_vend }}</td>
              <td>{{ store.fmt(row.PrecioVenta) }}</td>
              <td><span class="badge badge-red">{{ row.margen_pct }}%</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else style="padding: 10px; color: var(--fg-muted)">No hay productos en alerta.</p>
      </div>
    </div>
    
    <div v-if="data && data.por_laboratorio.length" class="card" style="margin-top: 16px;">
      <SectionTitle icon="🏢" title="Rentabilidad por Laboratorio" />
      <BarChart :horizontal="false" formatTooltip="currency" :categories="topLabCat" :series="[{name: 'Utilidad', data: topLabData}]" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import BarChart from '../components/charts/BarChart.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'

const store = useDashboardStore()
const data = computed(() => store.data.rentabilidad)
const loading = computed(() => store.loading.rentabilidad)

onMounted(() => {
  if (store.status.ventas && store.status.inventario && !data.value) {
    store.fetchRentabilidad()
  }
})

const topRentCat = computed(() => data.value?.top_rentables?.map(d => d.nombre) || [])
const topRentData = computed(() => data.value?.top_rentables?.map(d => d.utilidad_total) || [])

const topLabCat = computed(() => data.value?.por_laboratorio?.map(d => d.lab) || [])
const topLabData = computed(() => data.value?.por_laboratorio?.map(d => d.utilidad_total) || [])
</script>
