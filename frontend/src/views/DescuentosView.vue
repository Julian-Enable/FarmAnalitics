<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <TicketPercent size="32" color="var(--accent)" />
        <h2 style="margin:0;">Descuentos — Fuga de margen</h2>
      </div>
      <p style="margin-top:8px;">Cuántos pesos de descuento se dan, por plan, sede, cajero y producto. Detecta descuentos anormales.</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Por qué importa?</strong> Cada peso de descuento sale directo de la utilidad. Aquí ves dónde y quién está regalando margen, y se marcan los cajeros con descuentos muy por encima de lo normal (control interno).</p>
    </ModuleInfo>

    <div class="filters-bar" style="margin-bottom:16px;">
      <div class="filter-group"><label>Fecha Inicio</label><input type="date" v-model="filters.fecha_ini" @change="applyFilters" /></div>
      <div class="filter-group"><label>Fecha Fin</label><input type="date" v-model="filters.fecha_fin" @change="applyFilters" /></div>
    </div>

    <div v-if="store.errors.descuentos" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">{{ store.errors.descuentos }}</div>

    <div v-if="loading" class="kpi-grid kpi-grid-4"><div v-for="i in 4" :key="i" class="card skeleton" style="height:100px;"></div></div>

    <template v-else-if="data && data.kpis">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom:16px;">
        <KpiCard :icon="TicketPercent" label="Total Descontado" :value="store.fmt(data.kpis.total_descontado)" />
        <KpiCard :icon="Hash" label="Líneas con Descuento" :value="store.fmtN(data.kpis.n_lineas)" />
        <KpiCard :icon="DollarSign" label="Descuento Promedio" :value="store.fmt(data.kpis.descuento_promedio)" />
        <KpiCard :icon="Users" label="Cajeros" :value="store.fmtN(data.kpis.n_cajeros)" />
      </div>

      <div v-if="data.outliers?.length" class="card" style="margin-bottom:16px;border-color:#fecdd3;background:#fff8f8;">
        <SectionTitle :icon="AlertTriangle" title="⚠️ Cajeros con descuentos anormalmente altos" />
        <div style="overflow-x:auto;">
          <table class="data-table">
            <thead><tr><th>Cajero</th><th>Total descontado</th><th># Líneas</th><th>Nivel de alerta</th></tr></thead>
            <tbody>
              <tr v-for="o in data.outliers" :key="o.Cajero">
                <td style="font-weight:600;">{{ o.Cajero }}</td>
                <td style="color:var(--red);font-weight:600;">{{ store.fmt(o.total) }}</td>
                <td>{{ store.fmtN(o.n) }}</td>
                <td><span class="badge badge-red">{{ o.score }}× sobre lo normal</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <SectionTitle :icon="TrendingUp" title="Tendencia mensual de descuentos" />
          <LineChart v-if="tendCat.length" :categories="tendCat" :series="[{ name: 'Descuento', data: tendData }]" />
        </div>
        <div class="card">
          <SectionTitle :icon="Store" title="Descuento por sede" />
          <BarChart v-if="sedeCat.length" :horizontal="true" formatTooltip="currency" :categories="sedeCat" :series="[{ name: 'Descuento', data: sedeData }]" />
        </div>
        <div class="card">
          <SectionTitle :icon="Users" title="Descuento por cajero" />
          <BarChart v-if="cajCat.length" :horizontal="true" formatTooltip="currency" :categories="cajCat" :series="[{ name: 'Descuento', data: cajData }]" />
        </div>
        <div class="card">
          <SectionTitle :icon="Tag" title="Descuento por plan/promoción" />
          <BarChart v-if="planCat.length" :horizontal="true" formatTooltip="currency" :categories="planCat" :series="[{ name: 'Descuento', data: planData }]" />
        </div>

        <div class="card" style="grid-column: span 2;">
          <div class="section-header-row">
            <SectionTitle :icon="Package" title="Productos con más descuento" />
            <button class="export-btn" @click="exportProductos"><Download size="16" /> Exportar CSV</button>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead><tr><th>Referencia</th><th>Producto</th><th># Veces</th><th>Total descontado</th></tr></thead>
              <tbody>
                <tr v-for="p in (data.por_producto || []).slice(0, paginaProd * 15)" :key="p.Referencia">
                  <td style="font-size:11px;">{{ p.Referencia }}</td>
                  <td :title="p.Descripcion">{{ p.nombre }}</td>
                  <td>{{ store.fmtN(p.n) }}</td>
                  <td style="font-weight:600;color:var(--red);">{{ store.fmt(p.total) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="data.por_producto && paginaProd * 15 < data.por_producto.length" class="btn-secondary" style="margin-top:10px;" @click="paginaProd++">Ver más</button>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><TicketPercent size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Se requieren los descuentos. Actualiza la información desde tu PC.</p>
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
import LineChart from '../components/charts/LineChart.vue'
import { exportToCSV } from '../utils/export'
import { TicketPercent, Hash, DollarSign, Users, AlertTriangle, TrendingUp, Store, Tag, Package, Download } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.descuentos)
const loading = computed(() => store.loading.descuentos)
const filters = ref({ fecha_ini: '', fecha_fin: '' })
const paginaProd = ref(1)

function applyFilters() {
  const p = {}
  if (filters.value.fecha_ini) p.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) p.fecha_fin = filters.value.fecha_fin
  store.fetchDescuentos(p)
}

const tendCat = computed(() => (data.value?.tendencia || []).map(t => t.mes))
const tendData = computed(() => (data.value?.tendencia || []).map(t => t.total))
const sedeCat = computed(() => (data.value?.por_sede || []).map(s => s['Punto Venta']))
const sedeData = computed(() => (data.value?.por_sede || []).map(s => Math.round(s.total)))
const cajCat = computed(() => (data.value?.por_cajero || []).slice(0, 12).map(c => c.Cajero))
const cajData = computed(() => (data.value?.por_cajero || []).slice(0, 12).map(c => Math.round(c.total)))
const planCat = computed(() => (data.value?.por_plan || []).slice(0, 10).map(p => (p.Plan || '').substring(0, 28)))
const planData = computed(() => (data.value?.por_plan || []).slice(0, 10).map(p => Math.round(p.total)))

function exportProductos() {
  const cols = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Producto' },
    { key: 'n', label: 'Veces' },
    { key: 'total', label: 'Total descontado' },
  ]
  exportToCSV(data.value?.por_producto || [], cols, 'Descuentos_por_Producto')
}

onMounted(() => { if (store.status.descuentos && !data.value) applyFilters() })
</script>
