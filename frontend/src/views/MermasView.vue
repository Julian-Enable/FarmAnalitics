<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <PackageMinus size="32" color="var(--accent)" />
        <h2 style="margin:0;">Mermas y Ajustes de Inventario</h2>
      </div>
      <p style="margin-top:8px;">Pérdida real de inventario (avería, vencimiento, faltantes) separada de las correcciones que no son pérdida.</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Qué es pérdida y qué no?</strong> Los ajustes negativos se clasifican por su motivo:</p>
      <ul style="margin-left:20px;margin-top:8px;">
        <li><strong>Pérdida real:</strong> avería/daño, vencimiento, faltantes de conteo y consumo interno. <em>Esto sí cuesta plata.</em></li>
        <li><strong>Correcciones (no es pérdida):</strong> cambios de unidad de medida, trocados, traslados y ajustes de cargue.</li>
      </ul>
    </ModuleInfo>

    <div class="filters-bar" style="margin-bottom:16px;">
      <div class="filter-group"><label>Fecha Inicio</label><input type="date" v-model="filters.fecha_ini" @change="applyFilters" /></div>
      <div class="filter-group"><label>Fecha Fin</label><input type="date" v-model="filters.fecha_fin" @change="applyFilters" /></div>
    </div>

    <div v-if="store.errors.mermas" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">{{ store.errors.mermas }}</div>

    <div v-if="loading" class="kpi-grid kpi-grid-4"><div v-for="i in 4" :key="i" class="card skeleton" style="height:100px;"></div></div>

    <template v-else-if="data && data.kpis">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom:16px;">
        <KpiCard :icon="PackageMinus" label="Pérdida Real" :value="store.fmt(data.kpis.merma_total)" />
        <KpiCard :icon="Package" label="Unidades Perdidas" :value="store.fmtN(data.kpis.merma_unidades)" />
        <KpiCard :icon="Wrench" label="Correcciones (no es pérdida)" :value="store.fmt(data.kpis.correcciones_total)" />
        <KpiCard :icon="AlertTriangle" label="Productos Afectados" :value="store.fmtN(data.kpis.productos_afectados)" />
      </div>

      <div class="grid-2">
        <div class="card">
          <SectionTitle :icon="PieChartIcon" title="Ajustes por motivo (pérdida vs corrección)" />
          <BarChart v-if="catCat.length" :horizontal="true" formatTooltip="currency" :categories="catCat" :series="[{ name: 'Valor', data: catData }]" />
        </div>
        <div class="card">
          <SectionTitle :icon="Store" title="Pérdida real por sede" />
          <BarChart v-if="sedeCat.length" :horizontal="true" formatTooltip="currency" :categories="sedeCat" :series="[{ name: 'Pérdida', data: sedeData }]" />
        </div>

        <div class="card" style="grid-column: span 2;">
          <div class="section-header-row">
            <SectionTitle :icon="AlertTriangle" title="Productos con más pérdida" />
            <button class="export-btn" @click="exportProductos"><Download size="16" /> Exportar CSV</button>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead><tr><th>Referencia</th><th>Producto</th><th>Unidades</th><th>Pérdida ($)</th></tr></thead>
              <tbody>
                <tr v-for="p in (data.por_producto || []).slice(0, paginaProd * 15)" :key="p.Referencia">
                  <td style="font-size:11px;">{{ p.Referencia }}</td>
                  <td :title="p.Descripcion">{{ p.nombre }}</td>
                  <td>{{ store.fmtN(p.uds) }}</td>
                  <td style="font-weight:600;color:var(--red);">{{ store.fmt(p.valor) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="data.por_producto && paginaProd * 15 < data.por_producto.length" class="btn-secondary" style="margin-top:10px;" @click="paginaProd++">Ver más</button>
        </div>

        <div class="card" style="grid-column: span 2;" v-if="data.por_usuario?.length">
          <SectionTitle :icon="Users" title="Pérdida registrada por usuario" />
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead><tr><th>Usuario</th><th># Ajustes</th><th>Unidades</th><th>Pérdida ($)</th></tr></thead>
              <tbody>
                <tr v-for="u in data.por_usuario" :key="u.usuario">
                  <td style="font-weight:600;">{{ u.usuario }}</td>
                  <td>{{ store.fmtN(u.n) }}</td>
                  <td>{{ store.fmtN(u.uds) }}</td>
                  <td style="font-weight:600;color:var(--red);">{{ store.fmt(u.valor) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><PackageMinus size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Se requieren los ajustes de inventario. Actualiza la información desde tu PC.</p>
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
import { PackageMinus, Package, Wrench, AlertTriangle, Store, Users, Download, PieChart as PieChartIcon } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.mermas)
const loading = computed(() => store.loading.mermas)
const filters = ref({ fecha_ini: '', fecha_fin: '' })
const paginaProd = ref(1)

function applyFilters() {
  const p = {}
  if (filters.value.fecha_ini) p.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) p.fecha_fin = filters.value.fecha_fin
  store.fetchMermas(p)
}

const catCat = computed(() => (data.value?.por_categoria || []).map(c => c.categoria + (c.es_merma ? '' : ' (corrección)')))
const catData = computed(() => (data.value?.por_categoria || []).map(c => Math.round(c.valor)))
const sedeCat = computed(() => (data.value?.por_sede || []).map(s => s['Punto Venta']))
const sedeData = computed(() => (data.value?.por_sede || []).map(s => Math.round(s.valor)))

function exportProductos() {
  const cols = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Producto' },
    { key: 'uds', label: 'Unidades' },
    { key: 'valor', label: 'Perdida' },
  ]
  exportToCSV(data.value?.por_producto || [], cols, 'Mermas_por_Producto')
}

onMounted(() => { if (store.status.mermas && !data.value) applyFilters() })
</script>
