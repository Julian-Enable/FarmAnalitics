<template>
  <div>
    <div class="page-header">
      <h2>🧠 Inventario Inteligente</h2>
      <p>Control de reabastecimiento por clasificación ABC y análisis de cobertura</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Identificar qué necesitas comprar con urgencia, priorizando los productos más rentables, y dónde tienes dinero estancado.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Clasificación ABC:</strong> Calculada dinámicamente según los ingresos que genera cada producto. <strong>A</strong> (80% del ingreso, vitales), <strong>B</strong> (15%), <strong>C</strong> (5%).</li>
        <li><strong>Rotación y Cobertura:</strong> Mide la velocidad de venta diaria y calcula para cuántos días te alcanza el stock actual.</li>
        <li><strong>Reabastecer:</strong> Alertas de productos con stock crítico (&le; 15 días) que SÍ tienen rotación (se están vendiendo).</li>
        <li><strong>Inventario Quieto:</strong> Dinero atrapado en productos que llevan más de 60 días sin venderse.</li>
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
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard icon="⚠️" label="Reabastecer (Con Demanda)" :value="store.fmtN(data.kpis.bajo_stock)" />
      <KpiCard icon="🛑" label="Agotado (0 Stock, rotando)" :value="store.fmtN(data.kpis.sin_stock)" />
      <KpiCard icon="🐢" label="Prods. Sin Rotación (>60d)" :value="store.fmtN(data.kpis.inventario_quieto)" />
      <KpiCard icon="💸" label="Capital Inmovilizado" :value="store.fmt(data.kpis.capital_quieto)" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon">📦</div>
      <h3>Faltan datos</h3>
      <p>Sube el archivo de **Inventario** y **Ventas** para calcular la rotación cruzada.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Tabla de Bajo Stock -->
      <div class="card" style="grid-column: span 2;">
        <SectionTitle icon="📋" title="Reabastecer (Bajo Mínimo y Con Demanda)" />
        <div style="max-height: 400px; overflow-y: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Clase</th>
                <th>Referencia</th>
                <th>Descripción</th>
                <th>Rotación (diaria)</th>
                <th>Stock Actual</th>
                <th>Cobertura</th>
                <th>Déficit Sugerido</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.bajo_stock_tabla" :key="row.Referencia">
                <td style="text-align: center;">
                  <span class="badge" 
                        :class="{'badge-green': row.clasificacion_abc === 'A', 'badge-amber': row.clasificacion_abc === 'B', 'badge-red': row.clasificacion_abc === 'C'}">
                    {{ row.clasificacion_abc }}
                  </span>
                </td>
                <td>{{ row.Referencia }}</td>
                <td>{{ row.Descripcion?.substring(0, 35) }}</td>
                <td>{{ row.rotacion_diaria > 0 ? row.rotacion_diaria.toFixed(2) : '0.00' }} uds/día</td>
                <td><span class="badge" :class="row.Total === 0 ? 'badge-red' : 'badge-amber'">{{ store.fmtN(row.Total) }}</span></td>
                <td>
                  <span class="badge" :class="row.cobertura_dias < 7 ? 'badge-red' : 'badge-amber'">
                    {{ row.cobertura_dias < 9999 ? Math.round(row.cobertura_dias) + ' d' : '+999 d' }}
                  </span>
                </td>
                <td><span style="color: var(--red); font-weight: 600;">-{{ store.fmtN(row.deficit) }}</span></td>
              </tr>
              <tr v-if="!data.bajo_stock_tabla.length">
                <td colspan="7" style="text-align: center; color: var(--fg-muted);">No hay alertas urgentes de reabastecimiento.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top Déficit -->
      <div class="card">
        <SectionTitle icon="📉" title="Top 15 Mayor Déficit (Unidades)" />
        <BarChart v-if="topDefCat.length" :horizontal="true" :categories="topDefCat" :series="[{name: 'Déficit', data: topDefData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay productos con déficit urgente.</p>
      </div>
      
      <!-- Top Capital Inmovilizado -->
      <div class="card">
        <SectionTitle icon="💸" title="Top 15 Mayor Capital Inmovilizado" />
        <BarChart v-if="topQuietoCat.length" :horizontal="true" formatTooltip="currency" :categories="topQuietoCat" :series="[{name: 'Capital Inmovilizado', data: topQuietoData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay capital inmovilizado destacable.</p>
      </div>
    </div>

    <div v-if="data" class="grid-2" style="margin-top: 16px;">
      <!-- Tabla de Inventario Quieto -->
      <div class="card" style="grid-column: span 2;">
        <SectionTitle icon="🐢" title="Inventario Quieto (Sin Ventas > 60 Días)" />
        <div style="max-height: 400px; overflow-y: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Referencia</th>
                <th>Descripción</th>
                <th>Días Sin Venta</th>
                <th>Stock</th>
                <th>Capital Atrapado</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.inventario_quieto_tabla" :key="row.Referencia">
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

const store = useDashboardStore()
const data = computed(() => store.data.inventario)
const loading = computed(() => store.loading.inventario)

const sedeSeleccionada = ref('Todas')

function applyFilters() {
  store.fetchInventario(sedeSeleccionada.value)
}

onMounted(() => {
  if (store.status.inventario && !data.value) {
    store.fetchInventario()
  }
})

const topDefCat = computed(() => data.value?.top_deficit?.map(d => d.nombre) || [])
const topDefData = computed(() => data.value?.top_deficit?.map(d => d.deficit) || [])

const topQuietoCat = computed(() => data.value?.top_quieto?.map(d => d.nombre) || [])
const topQuietoData = computed(() => data.value?.top_quieto?.map(d => d.capital_inmovilizado) || [])
</script>
