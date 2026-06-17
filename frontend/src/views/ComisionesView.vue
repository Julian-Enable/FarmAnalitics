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
        <KpiCard :icon="BadgePercent" label="Productos en comisión HOY" :value="store.fmtN(data.kpis.productos_comision_hoy)" />
        <KpiCard :icon="DollarSign" label="Valor Comisionable (periodo)" :value="store.fmt(data.kpis.valor_total)" />
        <KpiCard :icon="Package" label="Unidades Comisionables (periodo)" :value="store.fmtN(data.kpis.unidades_total)" />
        <KpiCard :icon="Users" label="Vendedores (periodo)" :value="store.fmtN(data.kpis.n_vendedores)" />
      </div>
      <p style="margin:-8px 0 16px;color:var(--fg-muted);font-size:12px;">
        <strong>Productos en comisión HOY</strong> es la foto actual (no cambia con el filtro de fechas; la comisión varía a diario).
        El resto corresponde a lo vendido <strong>con comisión</strong> en el periodo seleccionado.
      </p>

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

        <!-- Catalogo de productos en comision HOY + stock actual -->
        <div class="card" style="grid-column: span 2;" v-if="data.catalogo?.length">
          <div class="section-header-row">
            <SectionTitle :icon="BadgePercent" :title="'Catálogo de productos en comisión HOY (' + store.fmtN(data.catalogo.length) + ') — stock actual'" />
            <button class="export-btn" @click="exportCatalogo"><Download size="16" /> Exportar catálogo</button>
          </div>
          <input v-model="buscarCat" placeholder="🔍 Buscar por producto, referencia o laboratorio..." style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:12px;" />
          <p style="margin:0 0 10px;color:var(--fg-muted);font-size:12px;">Foto de hoy: lo que está en comisión y cuántas unidades hay para vender. No cambia con el filtro de fechas.</p>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Referencia</th><th>Producto</th><th>Laboratorio</th>
                  <th>Precio Venta</th><th>Stock Total</th>
                  <th v-for="s in data.sedes_catalogo" :key="s">{{ s }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in catalogoPag" :key="p.Referencia">
                  <td style="font-size:11px;font-variant-numeric:tabular-nums;">{{ p.Referencia }}</td>
                  <td :title="p.Descripcion">{{ (p.Descripcion || '').substring(0, 38) }}</td>
                  <td style="font-size:11px;">{{ (p.Laboratorio || '').substring(0, 18) }}</td>
                  <td>{{ store.fmt(p.precio_venta) }}</td>
                  <td style="font-weight:700;" :style="{ color: p.stock_total > 0 ? 'var(--green)' : 'var(--red)' }">{{ store.fmtN(p.stock_total) }}</td>
                  <td v-for="s in data.sedes_catalogo" :key="s">{{ store.fmtN(p[s] || 0) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <Paginator v-model="pageCat" :totalItems="catalogoFiltrado.length" :itemsPerPage="20" />
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
import { ref, computed, onMounted, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import BarChart from '../components/charts/BarChart.vue'
import Paginator from '../components/ui/Paginator.vue'
import { exportToCSV } from '../utils/export'
import { BadgePercent, DollarSign, Package, Users, ClipboardList, Download, TrendingUp } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.comisiones)
const loading = computed(() => store.loading.comisiones)
const filters = ref({ fecha_ini: '', fecha_fin: '', sede: 'Todas' })
const metric = ref('valor')
const paginaProductos = ref(1)
const buscarCat = ref('')
const pageCat = ref(1)

const catalogoFiltrado = computed(() => {
  const q = buscarCat.value.trim().toLowerCase()
  const list = data.value?.catalogo || []
  if (!q) return list
  return list.filter(p =>
    (p.Descripcion || '').toLowerCase().includes(q) ||
    String(p.Referencia || '').toLowerCase().includes(q) ||
    (p.Laboratorio || '').toLowerCase().includes(q))
})
const catalogoPag = computed(() => catalogoFiltrado.value.slice((pageCat.value - 1) * 20, pageCat.value * 20))
watch(buscarCat, () => { pageCat.value = 1 })

function exportCatalogo() {
  const base = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Producto' },
    { key: 'Laboratorio', label: 'Laboratorio' },
    { key: 'precio_venta', label: 'Precio Venta' },
    { key: 'stock_total', label: 'Stock Total' },
  ]
  const sedes = (data.value?.sedes_catalogo || []).map(s => ({ key: s, label: s }))
  exportToCSV(catalogoFiltrado.value, [...base, ...sedes], 'Catalogo_Productos_Comision')
}

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
