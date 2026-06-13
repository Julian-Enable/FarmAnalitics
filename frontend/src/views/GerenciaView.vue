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

    <ModuleInfo>
      <p><strong>¿Qué te muestra esta página?</strong> Es tu asistente de operaciones diarias. Aquí encuentras acciones concretas basadas en datos y anomalías de tus ventas e inventario:</p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Reporte Diario:</strong> Resumen ejecutivo de cómo te fue ayer y cómo va el mes.</li>
        <li><strong>Sugerido de Traslado:</strong> Calcula si hay exceso de stock de un producto en una sede y faltante en otra, sugiriendo moverlo antes de comprar más. Filtra picos esporádicos para no sobre-reaccionar.</li>
        <li><strong>Pedido Automático por Proveedor:</strong> Agrupa todos los productos que están bajos de stock y te sugiere la compra agrupada por proveedor.</li>
        <li><strong>Fugas de Margen:</strong> Productos que estás vendiendo mucho pero con un margen de ganancia críticamente bajo (&lt;8%).</li>
        <li><strong>Anomalías:</strong> Detecta tickets inusualmente grandes, ventas de productos atípicos, caídas abruptas de venta en sedes o costos que subieron más del 20% de golpe.</li>
        <li><strong>⚠️ Ventas Esporádicas (Ícono Amarillo):</strong> Si ves este ícono, significa que el sistema detectó una venta inusual (ej. licitación) y la <strong>excluyó</strong> del cálculo de compras y traslados para no pedir de más.</li>
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
      <div class="filter-group" style="justify-content:flex-end;">
        <button class="btn-secondary" style="margin-top:18px;" @click="clearDates">Limpiar fechas</button>
      </div>
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
          <KpiCard :icon="DollarSign" label="Ventas último día" :value="store.fmt(data.reporte_diario.resumen.ventas_ayer || 0)" />
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
              <Download size="16" /> Descargar Todo (Excel)
            </button>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th v-for="col in proveedorCols" :key="col.key">{{ col.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="(row, idx) in (data.pedidos.proveedores || []).slice(0, 12)" 
                  :key="idx"
                  @click="selectedProvider = row.proveedor"
                  :style="{ 
                    cursor: 'pointer', 
                    background: selectedProvider === row.proveedor ? 'rgba(59, 130, 246, 0.15)' : '',
                    fontWeight: selectedProvider === row.proveedor ? '700' : 'normal'
                  }"
                >
                  <td v-for="col in proveedorCols" :key="col.key">
                    {{ col.formatter ? col.formatter(row[col.key], row) : row[col.key] }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Listado de productos para el proveedor seleccionado -->
          <div v-if="selectedProvider" class="order-details-section" style="margin-top: 16px; border-top: 1px solid var(--border); padding-top: 16px;">
            <div class="section-header-row" style="margin-bottom: 8px;">
              <h4 style="margin: 0; color: var(--fg); font-size: 13px; font-weight: 700;">
                📦 Productos a comprar para: <strong style="color: var(--accent);">{{ selectedProvider }}</strong>
              </h4>
              <button class="export-btn" style="font-size: 11px; padding: 4px 8px;" @click="exportSelectedProviderItems">
                <Download size="12" /> Excel Proveedor
              </button>
            </div>
            <div style="max-height: 250px; overflow-y: auto; border: 1px solid var(--border); border-radius: 4px;">
              <table class="data-table" style="margin-bottom: 0;">
                <thead style="position: sticky; top: 0; z-index: 10; background: var(--bg-card, #ffffff);">
                  <tr>
                    <th>Ref</th>
                    <th>Producto</th>
                    <th>Stock</th>
                    <th>Cant. Pedir</th>
                    <th>Costo Unit.</th>
                    <th>Total Estimado</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in filteredItems" :key="item.Referencia">
                    <td style="font-size: 11px; font-variant-numeric: tabular-nums;">{{ item.Referencia }}</td>
                    <td style="font-size: 11px;" :title="item.Descripcion">{{ item.Descripcion?.substring(0, 40) }}</td>
                    <td style="font-size: 11px;">{{ number(item.Total) }}</td>
                    <td style="font-weight: 700; color: var(--accent); font-size: 11px;">{{ number(item.cantidad_sugerida) }}</td>
                    <td style="font-size: 11px;">{{ money(item.Precio_Compra || item['Precio Compra']) }}</td>
                    <td style="font-weight: 600; color: var(--green); font-size: 11px;">{{ money(item.costo_estimado) }}</td>
                  </tr>
                  <tr v-if="!filteredItems.length">
                    <td colspan="6" style="text-align: center; color: var(--fg-muted); font-size: 11px;">No hay productos para este proveedor.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
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

      <div class="card" style="margin-top:16px;" v-if="data.descuentos_atipicos">
        <div class="section-header-row">
          <SectionTitle :icon="TicketPercent" :title="'Descuentos atípicos / poco comunes' + (data.descuentos_atipicos.kpis?.n_atipicos ? ' (' + store.fmtN(data.descuentos_atipicos.kpis.n_atipicos) + ' · ' + store.fmt(data.descuentos_atipicos.kpis.valor_atipico) + ')' : '')" />
          <button class="export-btn" @click="exportRows(data.descuentos_atipicos.lineas, descAtipCols, 'Descuentos_Atipicos')">
            <Download size="16" /> CSV
          </button>
        </div>
        <p style="padding:0 0 8px;color:var(--fg-muted);font-size:12px;">
          Descuentos que no coinciden con lo que dice su plan (sobre-descuento), de planes casi nunca usados, o de un valor inusualmente alto. Para revisar/controlar.
        </p>
        <SimpleTable v-if="data.descuentos_atipicos.lineas?.length" :rows="data.descuentos_atipicos.lineas" :cols="descAtipCols" :limit="20" />
        <p v-else style="padding:10px;color:var(--fg-muted);">Sin descuentos atípicos en el periodo. 👍</p>
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

      <div v-if="data.rentabilidad.sin_costo?.length" class="card" style="margin-top:16px;">
        <SectionTitle :icon="AlertTriangle" :title="'Productos sin costo confiable (' + (data.rentabilidad.kpis.sin_costo || 0) + ') — cargar costo de compra'" />
        <p style="padding:0 0 8px;color:var(--fg-muted);font-size:12px;">
          Se venden bien pero no tienen registro de compra ni costo en el catálogo, así que se excluyen de los cálculos de margen y de las alertas de "vendido bajo costo" para no distorsionar las cifras. Cárgales el precio de compra para que entren al análisis.
        </p>
        <SimpleTable :rows="data.rentabilidad.sin_costo" :cols="sinCostoCols" :limit="15" />
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
import { ref, computed, watch, defineComponent, h, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import { exportToCSV } from '../utils/export'
import {
  AlertTriangle,
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
  TicketPercent,
  TrendingDown,
} from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.gerencia)
const loading = computed(() => store.loading.gerencia)

const filters = ref({ fecha_ini: '', fecha_fin: '' })

function applyFilters() {
  const params = {}
  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  store.fetchGerencia(params)
}

function clearDates() {
  filters.value.fecha_ini = ''
  filters.value.fecha_fin = ''
  store.fetchGerencia()
}

const money = value => store.fmt(Number(value || 0))
const number = value => store.fmtN(Math.round(Number(value || 0)))
const pct = value => `${Number(value || 0).toFixed(1)}%`

const selectedProvider = ref(null)

const filteredItems = computed(() => {
  if (!selectedProvider.value || !data.value?.pedidos?.items) return []
  return data.value.pedidos.items.filter(item => item.proveedor === selectedProvider.value)
})

watch(() => data.value?.pedidos?.proveedores, (newProv) => {
  if (newProv && newProv.length > 0 && !selectedProvider.value) {
    selectedProvider.value = newProv[0].proveedor
  }
}, { immediate: true })

function exportSelectedProviderItems() {
  if (!selectedProvider.value || !filteredItems.value.length) return
  const cols = [
    { key: 'Referencia', label: 'Referencia' },
    { key: 'Descripcion', label: 'Producto' },
    { key: 'Total', label: 'Stock Actual' },
    { key: 'cantidad_sugerida', label: 'Cantidad a Pedir' },
    { key: 'Precio Compra', label: 'Costo Unit.', formatter: v => v ? Math.round(v) : 0 },
    { key: 'costo_estimado', label: 'Costo Total', formatter: v => v ? Math.round(v) : 0 }
  ]
  exportToCSV(filteredItems.value, cols, `Pedido_${selectedProvider.value.replace(/\s+/g, '_')}`)
}

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
  { key: 'precio_compra', label: 'Costo Unit.', formatter: money },
  { key: 'precio_venta_prom', label: 'Venta Unit.', formatter: money },
  { key: 'cant_vend', label: 'Cant', formatter: number },
  { key: 'margen_pct', label: 'Margen', formatter: pct },
  { key: 'utilidad_total', label: 'Utilidad', formatter: money },
]
const TIPO_ANOMALIA_LABELS = {
  'Venta atipica producto': 'Pico de Venta Atípico',
  'Caida fuerte por sede': 'Caída de Venta en Sede',
  'Ticket atipico': 'Ticket de Venta Muy Alto',
  'Devoluciones altas por vendedor': 'Devoluciones Elevadas por Cajero',
  'Stock cero o negativo con venta reciente': 'Stock Cero con Venta Reciente',
  'Costo subio mas de 20%': 'Aumento de Costo > 20%',
  'Compra grande con baja rotacion': 'Compra Grande de Baja Rotación',
}

const anomaliaCols = [
  { 
    key: 'tipo', 
    label: 'Tipo de Anomalía',
    formatter: (v) => TIPO_ANOMALIA_LABELS[v] || v
  },
  { 
    key: 'severidad', 
    label: 'Severidad',
    formatter: (v) => {
      const s = String(v).toUpperCase()
      if (s === 'ALTA') return '🔴 ALTA'
      if (s === 'MEDIA') return '🟡 MEDIA'
      return '🟢 BAJA'
    }
  },
  { 
    key: 'detalle', 
    label: 'Detalle',
    formatter: (v, row) => {
      if (row.referencia) {
        return `[${row.referencia}] ${v}`
      }
      return v
    }
  },
  { 
    key: 'valor', 
    label: 'Valor Detectado',
    formatter: (v, row) => {
      const tipo = row.tipo
      if (tipo === 'Caida fuerte por sede') {
        return `${Number(v).toFixed(1)}% de caída`
      }
      if (tipo === 'Ticket atipico' || tipo === 'Costo subio mas de 20%' || tipo === 'Devoluciones altas por vendedor') {
        return money(v)
      }
      if (tipo === 'Venta atipica producto' || tipo === 'Compra grande con baja rotacion') {
        return `${number(v)} uds`
      }
      if (tipo === 'Stock cero o negativo con venta reciente') {
        return `Stock: ${number(v)}`
      }
      return v
    }
  },
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
const fmtFecha = (v) => { if (!v) return '—'; try { return new Date(v).toLocaleDateString('es-CO') } catch { return v } }
const descAtipCols = [
  { key: 'Fecha', label: 'Fecha', formatter: fmtFecha },
  { key: 'Factura', label: 'Factura' },
  { key: 'Punto Venta', label: 'Sede' },
  { key: 'Cajero', label: 'Cajero' },
  { key: 'Descripcion', label: 'Producto', formatter: (v) => String(v || '').substring(0, 28) },
  { key: 'Plan', label: 'Plan', formatter: (v) => String(v || '').substring(0, 26) },
  { key: 'Valor', label: 'Descuento', formatter: money },
  { key: 'motivo', label: 'Motivo' },
]
const sinCostoCols = [
  { key: 'nombre', label: 'Producto' },
  { key: 'cant_vend', label: 'Cant vendida', formatter: number },
  { key: 'ingreso_total', label: 'Ingreso', formatter: money },
  { key: 'precio_venta_prom', label: 'Venta Unit.', formatter: money },
  { key: 'costo_fuente', label: 'Fuente costo' },
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
