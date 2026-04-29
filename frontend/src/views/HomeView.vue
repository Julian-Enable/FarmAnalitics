<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <LayoutDashboard size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Centro de Comando</h2>
      </div>
      <p style="margin-top: 8px;">Signos vitales del negocio en tiempo real</p>
      <div class="accent-bar"></div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom: 20px;">
        <div v-for="i in 6" :key="i" class="card skeleton" style="height: 100px;"></div>
      </div>
    </div>

    <!-- Data loaded -->
    <template v-else-if="data">

      <!-- Row 1: KPI cards principales -->
      <div class="kpi-grid kpi-grid-4" style="margin-bottom: 20px;">
        <KpiCard :icon="DollarSign"  label="Ingresos Totales"   :value="store.fmt(data.kpis.ingresos)" />
        <KpiCard :icon="TrendingUp"  label="Utilidad Bruta"     :value="store.fmt(data.kpis.utilidad)" />
        <KpiCard :icon="Percent"     label="Margen Promedio"    :value="data.kpis.margen_pct != null ? data.kpis.margen_pct + '%' : '—'" />
        <KpiCard :icon="Package"     label="Unidades Vendidas"  :value="store.fmtN(data.kpis.unidades)" />
        <KpiCard :icon="Receipt"     label="Total Facturas"     :value="store.fmtN(data.kpis.facturas)" />
        <KpiCard :icon="CreditCard"  label="Ticket Promedio"    :value="store.fmt(data.kpis.ticket)" />
      </div>

      <!-- Row 2: Alertas críticas -->
      <div v-if="data.alertas" class="alert-strip">
        <div class="alert-card alert-red">
          <AlertOctagon size="20" />
          <div>
            <span class="alert-num">{{ data.alertas.productos_sin_stock }}</span>
            <span class="alert-label">Productos sin stock con demanda activa</span>
          </div>
        </div>
        <div class="alert-card alert-amber">
          <Warehouse size="20" />
          <div>
            <span class="alert-num">{{ store.fmt(data.alertas.capital_quieto) }}</span>
            <span class="alert-label">Capital inmovilizado en inventario quieto</span>
          </div>
        </div>
        <div class="alert-card alert-blue">
          <Activity size="20" />
          <div>
            <span class="alert-num">{{ store.fmtN(data.kpis.unidades) }}</span>
            <span class="alert-label">Unidades despachadas en el período</span>
          </div>
        </div>
      </div>

      <!-- Row 3: Gráficos -->
      <div class="grid-2" style="margin-top: 20px;">
        <!-- Tendencia de ingresos -->
        <div class="card">
          <SectionTitle :icon="LineChartIcon" title="Tendencia de Ingresos" />
          <LineChart v-if="tendenciaCat.length" :categories="tendenciaCat" :series="[{name: 'Ingresos', data: tendenciaData}]" />
          <p v-else class="empty-state" style="padding: 20px; color: var(--fg-muted);">Datos insuficientes para tendencia</p>
        </div>

        <!-- Ingresos por sede -->
        <div class="card">
          <SectionTitle :icon="Store" title="Ingresos por Sede" />
          <BarChart v-if="sedesCat.length" :horizontal="true" formatTooltip="currency" :categories="sedesCat" :series="[{name: 'Ingresos', data: sedesData}]" />
          <p v-else class="empty-state" style="padding: 20px; color: var(--fg-muted);">Datos insuficientes para sedes</p>
        </div>
      </div>

      <!-- Row 4: Top Productos y Top Vendedores -->
      <div class="grid-2" style="margin-top: 16px;">
        <!-- Top 5 Productos -->
        <div class="card">
          <SectionTitle :icon="Trophy" title="Top 5 Productos (por Ingreso)" />
          <table class="data-table" v-if="data.top_productos?.length">
            <thead>
              <tr>
                <th>#</th>
                <th>Producto</th>
                <th style="text-align:right;">Ingreso</th>
                <th style="text-align:right;">Participación</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in data.top_productos" :key="i">
                <td>
                  <span class="rank-badge" :class="i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : i === 2 ? 'rank-3' : 'rank-n'">
                    {{ i + 1 }}
                  </span>
                </td>
                <td>{{ p.nombre }}</td>
                <td style="text-align:right; font-weight:600;">{{ store.fmt(p.ingreso) }}</td>
                <td style="text-align:right;">
                  <div class="progress-bar-wrap">
                    <div class="progress-bar-fill" :style="{ width: topProdPct(p.ingreso) + '%' }"></div>
                    <span class="progress-label">{{ topProdPct(p.ingreso) }}%</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else style="padding: 20px; color: var(--fg-muted);">Carga el archivo de ventas para ver los productos.</p>
        </div>

        <!-- Top 5 Vendedores -->
        <div class="card">
          <SectionTitle :icon="Users" title="Top 5 Vendedores (por Ingreso)" />
          <table class="data-table" v-if="data.top_vendedores?.length">
            <thead>
              <tr>
                <th>#</th>
                <th>Vendedor</th>
                <th style="text-align:right;">Ingreso</th>
                <th style="text-align:right;">Participación</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(v, i) in data.top_vendedores" :key="i">
                <td>
                  <span class="rank-badge" :class="i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : i === 2 ? 'rank-3' : 'rank-n'">
                    {{ i + 1 }}
                  </span>
                </td>
                <td>{{ v.vendedor }}</td>
                <td style="text-align:right; font-weight:600;">{{ store.fmt(v.ingreso) }}</td>
                <td style="text-align:right;">
                  <div class="progress-bar-wrap">
                    <div class="progress-bar-fill" :style="{ width: topVendPct(v.ingreso) + '%' }"></div>
                    <span class="progress-label">{{ topVendPct(v.ingreso) }}%</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else style="padding: 20px; color: var(--fg-muted);">El archivo de ventas no contiene columna de Vendedor.</p>
        </div>
      </div>

    </template>

    <!-- Empty state -->
    <div v-else class="empty-state">
      <div class="empty-icon"><Activity size="48" color="var(--border)" /></div>
      <h3>Sin datos cargados</h3>
      <p>Sube tus archivos de ventas e inventario en el panel lateral para activar el Centro de Comando.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import LineChart from '../components/charts/LineChart.vue'
import BarChart from '../components/charts/BarChart.vue'
import {
  LayoutDashboard, DollarSign, TrendingUp, Percent, Package,
  Receipt, CreditCard, Activity, LineChart as LineChartIcon,
  Store, Trophy, Users, AlertOctagon, Warehouse
} from 'lucide-vue-next'

const store = useDashboardStore()
const data    = computed(() => store.data.resumen)
const loading = computed(() => store.loading.resumen)

onMounted(() => {
  if (store.status.ventas && !data.value) store.fetchResumen()
})

const tendenciaCat  = computed(() => data.value?.tendencia?.map(d => d.fecha) || [])
const tendenciaData = computed(() => data.value?.tendencia?.map(d => d.ingreso) || [])
const sedesCat      = computed(() => data.value?.sedes?.map(d => d.sede) || [])
const sedesData     = computed(() => data.value?.sedes?.map(d => d.ingresos) || [])

const topProdMax = computed(() => Math.max(...(data.value?.top_productos?.map(p => p.ingreso) || [1])))
const topVendMax = computed(() => Math.max(...(data.value?.top_vendedores?.map(v => v.ingreso) || [1])))

function topProdPct(ingreso) {
  return topProdMax.value > 0 ? Math.round((ingreso / topProdMax.value) * 100) : 0
}
function topVendPct(ingreso) {
  return topVendMax.value > 0 ? Math.round((ingreso / topVendMax.value) * 100) : 0
}
</script>
