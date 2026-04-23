<template>
  <div>
    <div class="page-header">
      <h2>🧠 Inventario Inteligente</h2>
      <p>Control de reabastecimiento por demanda y detección de capital inmovilizado</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Identificar qué necesitas comprar con urgencia y dónde tienes dinero estancado.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>¿Cómo se calcula?:</strong> El sistema toma tu archivo de Inventario y lo cruza con tus Ventas para descubrir la fecha de la última venta de cada producto.</li>
        <li><strong>Reabastecer (Con Demanda):</strong> Filtra productos que están por debajo de su "Stock Mínimo", <strong>PERO</strong> solo te muestra los que sí se han vendido en los últimos 60 días. Evita que compres "huesos" o productos descontinuados.</li>
        <li><strong>Inventario Quieto (Capital Atrapado):</strong> Detecta productos que sí tienen stock, pero que llevan <strong>más de 60 días sin venderse</strong>. Luego multiplica esas unidades por su "Precio de Compra" para decirte exactamente cuántos pesos tienes inmovilizados.</li>
      </ul>
    </ModuleInfo>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard icon="⚠️" label="Reabastecer (Con Demanda)" :value="store.fmtN(data.kpis.bajo_stock)" />
      <KpiCard icon="🛑" label="Agotado (0 Stock)" :value="store.fmtN(data.kpis.sin_stock)" />
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
      <div class="card">
        <SectionTitle icon="📋" title="Reabastecer (Bajo Mínimo y Con Demanda)" />
        <div style="max-height: 400px; overflow-y: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Referencia</th>
                <th>Descripción</th>
                <th>Stock</th>
                <th>Mínimo</th>
                <th>Déficit</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.bajo_stock_tabla" :key="row.Referencia">
                <td>{{ row.Referencia }}</td>
                <td>{{ row.Descripcion?.substring(0, 25) }}</td>
                <td><span class="badge" :class="row.Total === 0 ? 'badge-red' : 'badge-amber'">{{ store.fmtN(row.Total) }}</span></td>
                <td>{{ store.fmtN(row['Stock Minimo']) }}</td>
                <td><span style="color: var(--red); font-weight: 600;">-{{ store.fmtN(row.deficit) }}</span></td>
              </tr>
              <tr v-if="!data.bajo_stock_tabla.length">
                <td colspan="5" style="text-align: center; color: var(--fg-muted);">No hay alertas urgentes de reabastecimiento.</td>
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
    </div>

    <div v-if="data" class="grid-2" style="margin-top: 16px;">
      <!-- Tabla de Inventario Quieto -->
      <div class="card">
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
                <td>{{ row.Descripcion?.substring(0, 25) }}</td>
                <td><span class="badge badge-red">{{ row.dias_sin_venta >= 999 ? 'NUNCA' : row.dias_sin_venta + ' d' }}</span></td>
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

      <!-- Top Capital Inmovilizado -->
      <div class="card">
        <SectionTitle icon="💸" title="Top 15 Mayor Capital Inmovilizado" />
        <BarChart v-if="topQuietoCat.length" :horizontal="true" formatTooltip="currency" :categories="topQuietoCat" :series="[{name: 'Capital Inmovilizado', data: topQuietoData}]" />
        <p v-else style="padding: 10px; color: var(--fg-muted);">No hay capital inmovilizado destacable.</p>
      </div>
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
const data = computed(() => store.data.inventario)
const loading = computed(() => store.loading.inventario)

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
