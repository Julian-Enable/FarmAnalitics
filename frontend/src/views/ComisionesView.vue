<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <BadgePercent size="32" color="var(--accent)" />
        <h2 style="margin:0;">Comisiones</h2>
      </div>
      <p style="margin-top:8px;">Productos comisionables vendidos: cantidad y valor por vendedor, en el periodo que elijas.</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Qué te muestra esta página?</strong> Las ventas de los productos que tienen comisión, para que calcules la comisión con tu propia regla.</p>
      <ul style="margin-left:20px;margin-top:8px;">
        <li><strong>Cantidad:</strong> unidades vendidas de productos comisionables.</li>
        <li><strong>Valor:</strong> el monto en pesos de esas ventas (cantidad × precio de venta).</li>
        <li>No se usa el monto/% de comisión que calcula el POS; aquí tienes la base (cantidad y valor) para aplicar tu fórmula.</li>
      </ul>
    </ModuleInfo>

    <div class="filters-bar" style="margin-bottom:16px;">
      <div class="filter-group">
        <label>Fecha Inicio</label>
        <input type="date" v-model="filters.fecha_ini" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label>Fecha Fin</label>
        <input type="date" v-model="filters.fecha_fin" @change="applyFilters" />
      </div>
      <div class="filter-group">
        <label>Punto de Venta</label>
        <select v-model="filters.sede" @change="applyFilters">
          <option value="Todas">Todas</option>
          <option v-for="s in data?.lista_sedes || []" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
    </div>

    <div v-if="store.errors.comisiones" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.comisiones }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height:100px;"></div>
    </div>

    <template v-else-if="data">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom:16px;">
        <KpiCard :icon="DollarSign" label="Valor Comisionable" :value="store.fmt(data.kpis.valor_total)" />
        <KpiCard :icon="Package" label="Unidades Comisionables" :value="store.fmtN(data.kpis.unidades_total)" />
        <KpiCard :icon="Users" label="Vendedores" :value="store.fmtN(data.kpis.n_vendedores)" />
        <KpiCard :icon="BadgePercent" label="Productos Comisionables" :value="store.fmtN(data.kpis.n_productos)" />
      </div>

      <div class="grid-2">
        <!-- Tendencia mensual (ultimos 12 meses) -->
        <div class="card" style="grid-column: span 2;" v-if="tendCat.length">
          <div class="section-header-row">
            <SectionTitle :icon="TrendingUp" title="Histórico de comisionable por mes (últimos 12 meses)" />
            <div class="metric-toggle">
              <button :class="{ active: metric === 'valor' }" @click="metric = 'valor'">Valor</button>
              <button :class="{ active: metric === 'cantidad' }" @click="metric = 'cantidad'">Cantidad</button>
            </div>
          </div>
          <BarChart :categories="tendCat" :formatTooltip="metric === 'valor' ? 'currency' : ''"
                    :series="[{ name: metric === 'valor' ? 'Valor' : 'Cantidad', data: tendData }]" />
        </div>

        <!-- Por vendedor (grafico) -->
        <div class="card" style="grid-column: span 2;">
          <div class="section-header-row">
            <SectionTitle :icon="Users" title="Comisionable por vendedor" />
            <div class="metric-toggle">
              <button :class="{ active: metric === 'valor' }" @click="metric = 'valor'">Valor</button>
              <button :class="{ active: metric === 'cantidad' }" @click="metric = 'cantidad'">Cantidad</button>
            </div>
          </div>
          <BarChart v-if="vendCat.length" :horizontal="true" :formatTooltip="metric === 'valor' ? 'currency' : ''"
                    :categories="vendCat" :series="[{ name: metric === 'valor' ? 'Valor' : 'Cantidad', data: vendData }]" />
        </div>

        <!-- Tabla por vendedor -->
        <div class="card" style="grid-column: span 2;">
          <div class="section-header-row">
            <SectionTitle :icon="ClipboardList" title="Detalle por vendedor" />
            <button class="export-btn" @click="exportVendedores"><Download size="16" /> Exportar CSV</button>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead>
                <tr><th>Vendedor</th><th>Cantidad (uds)</th><th>Valor</th><th>Productos</th></tr>
              </thead>
              <tbody>
                <tr v-for="v in data.por_vendedor" :key="v.Vendedor">
                  <td style="font-weight:600;">{{ v.Vendedor }}</td>
                  <td>{{ store.fmtN(v.cantidad) }}</td>
                  <td style="font-weight:600;color:var(--green);">{{ store.fmt(v.valor) }}</td>
                  <td>{{ store.fmtN(v.productos) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Top productos comisionables -->
        <div class="card" style="grid-column: span 2;">
          <div class="section-header-row">
            <SectionTitle :icon="BadgePercent" title="Productos comisionables más vendidos" />
            <button class="export-btn" @click="exportDetalle"><Download size="16" /> Exportar detalle (vendedor × producto)</button>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead>
                <tr><th>Referencia</th><th>Producto</th><th>Cantidad (uds)</th><th>Valor</th><th>Vendedores</th></tr>
              </thead>
              <tbody>
                <tr v-for="p in (data.por_producto || []).slice(0, paginaProductos * 15)" :key="p.Referencia">
                  <td style="font-size:11px;font-variant-numeric:tabular-nums;">{{ p.Referencia }}</td>
                  <td :title="p.Descripcion">{{ p.nombre }}</td>
                  <td>{{ store.fmtN(p.cantidad) }}</td>
                  <td style="color:var(--green);">{{ store.fmt(p.valor) }}</td>
                  <td>{{ store.fmtN(p.vendedores) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="data.por_producto && paginaProductos * 15 < data.por_producto.length"
                  class="btn-secondary" style="margin-top:10px;" @click="paginaProductos++">Ver más</button>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><BadgePercent size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Se requieren datos de comisiones. Actualiza la información desde tu PC para descargarlos.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import BarChart from '../components/charts/BarChart.vue'
import { exportToCSV } from '../utils/export'
import { BadgePercent, DollarSign, Package, Users, ClipboardList, Download, TrendingUp } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.comisiones)
const loading = computed(() => store.loading.comisiones)
const filters = ref({ fecha_ini: '', fecha_fin: '', sede: 'Todas' })
const metric = ref('valor')
const paginaProductos = ref(1)

function applyFilters() {
  const params = {}
  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  if (filters.value.sede && filters.value.sede !== 'Todas') params.sede = filters.value.sede
  store.fetchComisiones(params)
}

const vendCat = computed(() => (data.value?.por_vendedor || []).slice(0, 15).map(v => v.Vendedor))
const vendData = computed(() => (data.value?.por_vendedor || []).slice(0, 15).map(v => metric.value === 'valor' ? Math.round(v.valor) : v.cantidad))

// Tendencia: últimos 12 meses
const tend12 = computed(() => (data.value?.tendencia || []).slice(-12))
const tendCat = computed(() => tend12.value.map(t => t.mes_label))
const tendData = computed(() => tend12.value.map(t => metric.value === 'valor' ? Math.round(t.valor) : t.cantidad))

onMounted(() => {
  if (store.status.comisiones && !data.value) applyFilters()
})

function exportVendedores() {
  const cols = [
    { key: 'Vendedor', label: 'Vendedor' },
    { key: 'cantidad', label: 'Cantidad (uds)' },
    { key: 'valor', label: 'Valor' },
    { key: 'productos', label: 'Productos' },
  ]
  exportToCSV(data.value?.por_vendedor || [], cols, 'Comisiones_por_Vendedor')
}

function exportDetalle() {
  const cols = [
    { key: 'Vendedor', label: 'Vendedor' },
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Producto' },
    { key: 'cantidad', label: 'Cantidad (uds)' },
    { key: 'valor', label: 'Valor' },
  ]
  exportToCSV(data.value?.detalle || [], cols, 'Comisiones_Detalle_Vendedor_Producto')
}
</script>

<style scoped>
.metric-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.metric-toggle button {
  background: transparent;
  border: none;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  color: var(--fg-muted);
}
.metric-toggle button.active {
  background: var(--accent);
  color: #fff;
}
</style>
