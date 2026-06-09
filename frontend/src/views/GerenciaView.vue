<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <BriefcaseBusiness size="32" color="var(--accent)" />
        <h2 style="margin:0;">Gerencia Operativa</h2>
      </div>
      <p style="margin-top:8px;">Acciones sugeridas para abastecimiento, margen, anomalias y cierre diario.</p>
      <div class="accent-bar"></div>
    </div>

    <div v-if="store.errors.gerencia" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.gerencia }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 8" :key="i" class="card skeleton" style="height:100px;"></div>
    </div>

    <template v-else-if="data">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom:16px;">
        <KpiCard :icon="ArrowLeftRight" label="Traslados sugeridos" :value="store.fmtN(data.traslados.kpis.sugerencias || 0)" />
        <KpiCard :icon="ShoppingCart" label="Pedido sugerido" :value="store.fmt(data.pedidos.kpis.costo_estimado || 0)" />
        <KpiCard :icon="ShieldAlert" label="Anomalias" :value="store.fmtN(data.anomalias.kpis.total || 0)" />
        <KpiCard :icon="TrendingDown" label="Fugas de margen" :value="store.fmtN(data.rentabilidad.kpis.fugas_margen || 0)" />
      </div>

      <div class="card" style="margin-bottom:16px;">
        <SectionTitle :icon="SunMedium" :title="'Reporte diario' + (data.reporte_diario.fecha ? ' - ' + data.reporte_diario.fecha : '')" />
        <div class="kpi-grid kpi-grid-4" style="margin-top:12px;">
          <KpiCard :icon="DollarSign" label="Ventas ayer" :value="store.fmt(data.reporte_diario.resumen.ventas_ayer || 0)" />
          <KpiCard :icon="CalendarDays" label="Ventas mes actual" :value="store.fmt(data.reporte_diario.resumen.ventas_mes_actual || 0)" />
          <KpiCard :icon="PackageX" label="Agotados criticos" :value="store.fmtN(data.reporte_diario.agotados_criticos?.length || 0)" />
          <KpiCard :icon="Boxes" label="Capital quieto" :value="store.fmt(data.reporte_diario.resumen.capital_quieto || 0)" />
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="section-header-row">
            <SectionTitle :icon="ArrowLeftRight" title="Sugerido de traslado entre sedes" />
            <button class="export-btn" @click="exportRows(data.traslados.sugerencias, trasladoCols, 'Traslados_Sugeridos')">
              <Download size="16" /> CSV
            </button>
          </div>
          <SimpleTable :rows="data.traslados.sugerencias" :cols="trasladoCols" :limit="12" />
        </div>

        <div class="card">
          <div class="section-header-row">
            <SectionTitle :icon="ShoppingCart" title="Pedido automatico por proveedor" />
            <button class="export-btn" @click="exportRows(data.pedidos.items, pedidoCols, 'Pedido_Sugerido')">
              <Download size="16" /> CSV
            </button>
          </div>
          <SimpleTable :rows="data.pedidos.proveedores" :cols="proveedorCols" :limit="12" />
        </div>

        <div class="card">
          <div class="section-header-row">
            <SectionTitle :icon="TrendingDown" title="Rentabilidad real y fugas de margen" />
            <button class="export-btn" @click="exportRows(data.rentabilidad.bajo_margen_alta_venta, margenCols, 'Fugas_Margen')">
              <Download size="16" /> CSV
            </button>
          </div>
          <SimpleTable :rows="data.rentabilidad.bajo_margen_alta_venta" :cols="margenCols" :limit="12" />
        </div>

        <div class="card">
          <div class="section-header-row">
            <SectionTitle :icon="ShieldAlert" title="Detector de anomalias" />
            <button class="export-btn" @click="exportRows(data.anomalias.anomalias, anomaliaCols, 'Anomalias')">
              <Download size="16" /> CSV
            </button>
          </div>
          <SimpleTable :rows="data.anomalias.anomalias" :cols="anomaliaCols" :limit="14" />
        </div>
      </div>

      <div class="grid-2" style="margin-top:16px;">
        <div class="card">
          <SectionTitle :icon="Factory" title="Laboratorios: utilidad vs capital" />
          <SimpleTable :rows="data.rentabilidad.laboratorios_capital" :cols="labCols" :limit="15" />
        </div>
        <div class="card">
          <SectionTitle :icon="Store" title="Sedes con ingreso alto y baja utilidad" />
          <SimpleTable :rows="data.rentabilidad.sedes_ingreso_baja_utilidad" :cols="sedeCols" :limit="15" />
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><BriefcaseBusiness size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Se requieren ventas e inventario para generar acciones gerenciales.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import { exportToCSV } from '../utils/export'
import {
  ArrowLeftRight,
  Boxes,
  BriefcaseBusiness,
  CalendarDays,
  DollarSign,
  Download,
  Factory,
  PackageX,
  ShieldAlert,
  ShoppingCart,
  Store,
  SunMedium,
  TrendingDown,
} from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.gerencia)
const loading = computed(() => store.loading.gerencia)

const money = value => store.fmt(Number(value || 0))
const number = value => store.fmtN(Math.round(Number(value || 0)))
const pct = value => `${Number(value || 0).toFixed(1)}%`

const trasladoCols = [
  { key: 'Descripcion', label: 'Producto', formatter: (v, row) => row.uds_esporadicas_excluidas > 0 ? `${v} ⚠️ (-${number(row.uds_esporadicas_excluidas)})` : v },
  { key: 'origen', label: 'Origen' },
  { key: 'destino', label: 'Destino' },
  { key: 'cantidad_sugerida', label: 'Cant', formatter: number },
  { key: 'cobertura_destino', label: 'Cob destino' },
]
const proveedorCols = [
  { key: 'proveedor', label: 'Proveedor' },
  { key: 'items', label: 'Items', formatter: number },
  { key: 'unidades', label: 'Unid', formatter: number },
  { key: 'costo_estimado', label: 'Costo', formatter: money },
]
const pedidoCols = [
  { key: 'proveedor', label: 'Proveedor' },
  { key: 'Descripcion', label: 'Producto', formatter: (v, row) => row.uds_esporadicas_excluidas > 0 ? `${v} ⚠️ (-${number(row.uds_esporadicas_excluidas)})` : v },
  { key: 'cantidad_sugerida', label: 'Cant', formatter: number },
  { key: 'costo_estimado', label: 'Costo', formatter: money },
]
const margenCols = [
  { key: 'nombre', label: 'Producto' },
  { key: 'cant_vend', label: 'Cant', formatter: number },
  { key: 'margen_pct', label: 'Margen', formatter: pct },
  { key: 'utilidad_total', label: 'Utilidad', formatter: money },
]
const anomaliaCols = [
  { key: 'tipo', label: 'Tipo' },
  { key: 'severidad', label: 'Sev' },
  { key: 'detalle', label: 'Detalle' },
  { key: 'valor', label: 'Valor' },
]
const labCols = [
  { key: 'lab', label: 'Laboratorio' },
  { key: 'utilidad_total', label: 'Utilidad', formatter: money },
  { key: 'capital_actual', label: 'Capital', formatter: money },
  { key: 'utilidad_sobre_capital', label: 'U/Cap', formatter: pct },
]
const sedeCols = [
  { key: 'sede', label: 'Sede' },
  { key: 'ingreso_total', label: 'Ingreso', formatter: money },
  { key: 'utilidad_total', label: 'Utilidad', formatter: money },
  { key: 'margen_pct', label: 'Margen', formatter: pct },
]

const SimpleTable = defineComponent({
  props: { rows: Array, cols: Array, limit: { type: Number, default: 10 } },
  setup(props) {
    return () => {
      const rows = (props.rows || []).slice(0, props.limit)
      if (!rows.length) return h('p', { style: 'padding:10px;color:var(--fg-muted);' }, 'Sin alertas para mostrar.')
      return h('div', { style: 'overflow-x:auto;' }, [
        h('table', { class: 'data-table' }, [
          h('thead', [h('tr', props.cols.map(col => h('th', col.label)))]),
          h('tbody', rows.map((row, index) => h('tr', { key: index }, props.cols.map(col => {
            const value = row[col.key]
            return h('td', col.formatter ? col.formatter(value, row) : String(value ?? ''))
          }))))
        ])
      ])
    }
  }
})

onMounted(async () => {
  if (!data.value) await store.fetchGerencia()
})

function exportRows(rows, cols, filename) {
  exportToCSV(rows || [], cols, filename)
}
</script>
