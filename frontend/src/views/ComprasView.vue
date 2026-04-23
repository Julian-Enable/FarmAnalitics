<template>
  <div>
    <div class="page-header">
      <h2>⚖️ Conciliación y Cobertura (Compras vs Ventas)</h2>
      <p>Cálculo de Inventario Inicial por ingeniería inversa y días de cobertura de stock</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Objetivo:</strong> Reconstruir el historial exacto de tu inventario y predecir cuándo te quedarás sin stock.</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Ingeniería Inversa (Inv. Inicial):</strong> El sistema sabe cuánto tienes *ahora* (Inventario Actual). Sabe cuánto compraste y cuánto vendiste. Con esos 3 datos, viaja al pasado y calcula tu `Inventario Inicial = Actual + Vendido - Comprado`. Esto asegura un cuadre perfecto de tus productos.</li>
        <li><strong>Días del Periodo:</strong> Es la cantidad de días que hay entre la primera y última venta de tu archivo. Permite calcular a qué velocidad diaria se vende cada producto.</li>
        <li><strong>Cobertura (Días):</strong> Te dice para cuántos días te alcanza el inventario actual si se sigue vendiendo a ese mismo ritmo. <br><span style="color:var(--red);">Rojo: te queda para menos de 15 días.</span> <span style="color:var(--amber);">Amarillo: tienes exceso (>90 días).</span></li>
      </ul>
    </ModuleInfo>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    <div v-else-if="data" class="kpi-grid kpi-grid-4">
      <KpiCard icon="🛒" label="Total Comprado (Uds)" :value="store.fmtN(data.kpis.total_comprado)" />
      <KpiCard icon="📦" label="Total Vendido (Uds)" :value="store.fmtN(data.kpis.total_vendido)" />
      <KpiCard icon="⚠️" label="Items Sobrecomprados" :value="store.fmtN(data.kpis.n_sobre_compra)" />
      <KpiCard icon="⏱️" label="Días del Periodo" :value="data.kpis.dias_periodo + ' días'" />
    </div>
    <div v-else class="empty-state">
      <div class="empty-icon">⚖️</div>
      <h3>Faltan datos</h3>
      <p>Sube archivos de **Inventario, Compras y Ventas** para ejecutar la conciliación matemática.</p>
    </div>

    <div v-if="data" class="grid-2">
      <!-- Conciliación Matemática -->
      <div class="card" style="grid-column: span 2;">
        <SectionTitle icon="🧮" title="Flujo Exacto de Inventario (Conciliación)" />
        <div style="max-height: 400px; overflow-y: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Referencia</th>
                <th>Descripción</th>
                <th style="background: var(--bg); border-left: 1px solid var(--border);">Inv. Inicial (Calculado)</th>
                <th style="color: var(--green);">+ Comprado</th>
                <th style="color: var(--red);">- Vendido</th>
                <th style="background: var(--bg); border-right: 1px solid var(--border); font-weight: 700;">= Inv. Actual</th>
                <th>Cobertura (Días)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.comparativo" :key="row.Referencia">
                <td>{{ row.Referencia }}</td>
                <td>{{ row.Descripcion?.substring(0, 35) || 'N/A' }}</td>
                <td style="background: var(--bg); border-left: 1px solid var(--border);">{{ store.fmtN(row.inv_inicial) }}</td>
                <td style="color: var(--green);">{{ store.fmtN(row.uds_compradas) }}</td>
                <td style="color: var(--red);">{{ store.fmtN(row.uds_vendidas) }}</td>
                <td style="background: var(--bg); border-right: 1px solid var(--border); font-weight: 700;">{{ store.fmtN(row.inv_actual) }}</td>
                <td>
                  <span class="badge" 
                        :class="row.cobertura_dias < 15 ? 'badge-red' : (row.cobertura_dias > 90 ? 'badge-amber' : 'badge-green')">
                    {{ row.cobertura_dias >= 9999 ? '+999 d' : Math.round(row.cobertura_dias) + ' d' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top Proveedores -->
      <div class="card" style="grid-column: span 2;">
        <SectionTitle icon="🚚" title="Top 10 Proveedores (Unidades Compradas)" />
        <BarChart v-if="topProvCat.length" :horizontal="true" :categories="topProvCat" :series="[{name: 'Unidades', data: topProvData}]" />
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
const data = computed(() => store.data.compras)
const loading = computed(() => store.loading.compras)

onMounted(() => {
  if (store.status.ventas && store.status.compras && store.status.inventario && !data.value) {
    store.fetchCompras()
  }
})

const topProvCat = computed(() => data.value?.top_proveedores?.map(d => d.proveedor) || [])
const topProvData = computed(() => data.value?.top_proveedores?.map(d => d.unidades) || [])
</script>
