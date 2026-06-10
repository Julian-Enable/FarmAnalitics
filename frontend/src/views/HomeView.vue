<template>
  <div>

    <!-- Encabezado de periodo -->
    <div class="cmd-header">
      <div class="cmd-header-left">
        <div class="cmd-title-row">
          <LayoutDashboard size="22" />
          <h2>Centro de Comando</h2>
        </div>
        <p v-if="data?.periodo?.inicio" class="cmd-period">
          Periodo analizado:
          <strong>{{ formatFecha(data.periodo.inicio) }}</strong>
          a
          <strong>{{ formatFecha(data.periodo.fin) }}</strong>
          <span class="cmd-period-badge">{{ displayPeriodDays }} dias</span>
        </p>
        <p v-else class="cmd-period">Sube tus archivos para activar el analisis</p>
      </div>
      <div class="cmd-header-right" v-if="data">
        <div class="cmd-health-score" :class="healthClass">
          <span class="health-label">Salud del Negocio</span>
          <span class="health-value">{{ healthScore }}</span>
        </div>
      </div>
    </div>

    <div v-if="_store.status.ventas" class="filters-bar" style="margin-bottom: 16px;">
      <div class="filter-group">
        <label>Fecha Inicio</label>
        <input
          type="date"
          v-model="filters.fecha_ini"
          :min="minAllowedDate"
          :max="todayIso"
          @change="applyFilters"
        />
      </div>
      <div class="filter-group">
        <label>Fecha Fin</label>
        <input
          type="date"
          v-model="filters.fecha_fin"
          :min="minAllowedDate"
          :max="todayIso"
          @change="applyFilters"
        />
      </div>
    </div>

    <!-- Skeleton ──────────────────────────────────────────── -->
    <div v-if="loading">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom: 20px;">
        <div v-for="i in 6" :key="i" class="card skeleton" style="height: 90px;"></div>
      </div>
      <div class="card skeleton" style="height: 280px; margin-bottom: 16px;"></div>
    </div>

    <!-- ── Datos cargados ────────────────────────────────────── -->
    <template v-else-if="data">

      <!-- Fila 1: KPIs con variación -->
      <div class="kpi-grid kpi-grid-3" style="margin-bottom: 16px;">
        <div class="cmd-kpi-card">
          <div class="cmd-kpi-icon-wrap" style="background: #eff6ff;">
            <DollarSign size="18" color="#2563eb" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label">{{ data.devoluciones ? 'Ingresos Brutos' : 'Ingresos Totales' }}</span>
            <span class="cmd-kpi-value">{{ _store.fmt(data.kpis.ingresos) }}</span>
            <span v-if="data.devoluciones" class="cmd-kpi-sub" style="color: var(--green); font-weight: 600;">Neto: {{ _store.fmt(data.devoluciones.ingresos_netos) }}</span>
            <span v-else-if="data.kpis.variacion_ing != null" class="cmd-kpi-delta" :class="data.kpis.variacion_ing >= 0 ? 'delta-up' : 'delta-down'">
              <TrendingUp v-if="data.kpis.variacion_ing >= 0" size="12" />
              <TrendingDown v-else size="12" />
              {{ Math.abs(data.kpis.variacion_ing) }}% vs primera mitad
            </span>
          </div>
        </div>

        <div class="cmd-kpi-card">
          <div class="cmd-kpi-icon-wrap" style="background: #f0fdf4;">
            <Gem size="18" color="#16a34a" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label">Utilidad Bruta</span>
            <span class="cmd-kpi-value">{{ data.kpis.utilidad != null ? _store.fmt(data.kpis.utilidad) : '—' }}</span>
            <span v-if="data.kpis.margen_pct != null" class="cmd-kpi-sub">Margen: {{ data.kpis.margen_pct }}%</span>
          </div>
        </div>

        <div v-if="data.devoluciones" class="cmd-kpi-card" style="border: 1px solid var(--red-light); background: #fffcfc;">
          <div class="cmd-kpi-icon-wrap" style="background: #fee2e2;">
            <RotateCcw size="18" color="#ef4444" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label" style="color: var(--red);">Devoluciones (Notas Cr)</span>
            <span class="cmd-kpi-value" style="color: var(--red);">{{ _store.fmt(data.devoluciones.total_devuelto) }}</span>
            <div style="display:flex; justify-content:space-between; width:100%; align-items:center;">
              <span class="cmd-kpi-sub" style="color: var(--red);">Tasa: {{ data.devoluciones.tasa_pct }}%</span>
              <router-link to="/devoluciones" style="font-size:10px; color:var(--red); text-decoration:underline;">Ver detalle</router-link>
            </div>
          </div>
        </div>

        <div class="cmd-kpi-card">
          <div class="cmd-kpi-icon-wrap" style="background: #fdf4ff;">
            <CreditCard size="18" color="#9333ea" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label">Ticket Promedio</span>
            <span class="cmd-kpi-value">{{ _store.fmt(data.kpis.ticket) }}</span>
            <span v-if="data.kpis.variacion_ticket != null" class="cmd-kpi-delta" :class="data.kpis.variacion_ticket >= 0 ? 'delta-up' : 'delta-down'">
              <TrendingUp v-if="data.kpis.variacion_ticket >= 0" size="12" />
              <TrendingDown v-else size="12" />
              {{ Math.abs(data.kpis.variacion_ticket) }}% vs primera mitad
            </span>
          </div>
        </div>

        <div class="cmd-kpi-card">
          <div class="cmd-kpi-icon-wrap" style="background: #fff7ed;">
            <Package size="18" color="#ea580c" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label">Unidades Vendidas</span>
            <span class="cmd-kpi-value">{{ _store.fmtN(data.kpis.unidades) }}</span>
            <span v-if="data.kpis.variacion_und != null" class="cmd-kpi-delta" :class="data.kpis.variacion_und >= 0 ? 'delta-up' : 'delta-down'">
              <TrendingUp v-if="data.kpis.variacion_und >= 0" size="12" />
              <TrendingDown v-else size="12" />
              {{ Math.abs(data.kpis.variacion_und) }}% vs primera mitad
            </span>
          </div>
        </div>

        <div class="cmd-kpi-card">
          <div class="cmd-kpi-icon-wrap" style="background: #fefce8;">
            <Receipt size="18" color="#ca8a04" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label">Total Facturas</span>
            <span class="cmd-kpi-value">{{ _store.fmtN(data.kpis.facturas) }}</span>
            <span class="cmd-kpi-sub">{{ displayPeriodDays ? (data.kpis.facturas / displayPeriodDays).toFixed(1) + ' facturas/dia' : '' }}</span>
          </div>
        </div>

        <div class="cmd-kpi-card cmd-kpi-muted">
          <div class="cmd-kpi-icon-wrap" style="background: #f1f5f9;">
            <Activity size="18" color="#64748b" />
          </div>
          <div class="cmd-kpi-body">
            <span class="cmd-kpi-label">Uds/Factura Promedio</span>
            <span class="cmd-kpi-value">{{ data.kpis.facturas > 0 ? (data.kpis.unidades / data.kpis.facturas).toFixed(1) : '—' }}</span>
            <span class="cmd-kpi-sub">unidades por transacción</span>
          </div>
        </div>
      </div>

      <!-- Fila 2: Panel de Alertas (si hay inventario cruzado) -->
      <div v-if="data.alertas && hayAlertas" class="fire-panel">
        <div class="fire-panel-title">
          <Siren size="16" />
          Panel de Alertas — Acciones Urgentes
        </div>
        <div class="fire-panel-cards">
          <div v-if="data.alertas.sin_stock > 0" class="fire-card fire-critical">
            <div class="fire-card-icon"><OctagonX size="20" /></div>
            <div class="fire-card-body">
              <span class="fire-card-num">{{ data.alertas.sin_stock }}</span>
              <span class="fire-card-label">Productos sin stock<br><small>con demanda activa hoy</small></span>
            </div>
            <span class="fire-badge fire-badge-critical">CRÍTICO</span>
          </div>
          <div v-if="data.alertas.criticos_7d > 0" class="fire-card fire-warning">
            <div class="fire-card-icon"><Timer size="20" /></div>
            <div class="fire-card-body">
              <span class="fire-card-num">{{ data.alertas.criticos_7d }}</span>
              <span class="fire-card-label">Se agotan en &lt; 7 días<br><small>requieren pedido inmediato</small></span>
            </div>
            <span class="fire-badge fire-badge-warning">URGENTE</span>
          </div>
          <div v-if="data.alertas.atencion_15d > 0" class="fire-card fire-attention">
            <div class="fire-card-icon"><AlertTriangle size="20" /></div>
            <div class="fire-card-body">
              <span class="fire-card-num">{{ data.alertas.atencion_15d }}</span>
              <span class="fire-card-label">Se agotan en 7–15 días<br><small>planificar reabastecimiento</small></span>
            </div>
            <span class="fire-badge fire-badge-attention">ATENCIÓN</span>
          </div>
          <div v-if="data.alertas.capital_quieto > 0" class="fire-card fire-info">
            <div class="fire-card-icon"><Warehouse size="20" /></div>
            <div class="fire-card-body">
              <span class="fire-card-num">{{ _store.fmt(data.alertas.capital_quieto) }}</span>
              <span class="fire-card-label">Capital inmovilizado<br><small>inventario quieto +60 días</small></span>
            </div>
            <span class="fire-badge fire-badge-info">REVISAR</span>
          </div>
        </div>
      </div>

      <!-- Fila 3: Tendencia (ancho completo) + Sedes (lateral) -->
      <div class="cmd-main-grid" style="margin-top: 16px;">

        <!-- Tendencia de ingresos — ancho 2/3 -->
        <div class="card" style="grid-column: span 2;">
          <SectionTitle :icon="LineChartIcon" title="Tendencia de Ingresos (Semanal)" />
          <LineChart v-if="tendenciaCat.length" :categories="tendenciaCat" :series="[{name: 'Ingresos', data: tendenciaData}]" />
          <div v-else class="empty-state" style="padding: 40px 20px;">
            <Activity size="32" color="var(--border)" />
            <p style="margin-top: 8px; color: var(--fg-muted);">Sin datos de tendencia</p>
          </div>
        </div>

        <!-- Ingresos por sede — 1/3 -->
        <div class="card">
          <SectionTitle :icon="Store" title="Participación por Sede" />
          <div v-if="data.sedes?.length" class="sede-list">
            <div v-for="(s, i) in data.sedes" :key="i" class="sede-row">
              <div class="sede-row-top">
                <span class="sede-name">{{ s.sede }}</span>
                <span class="sede-value">{{ _store.fmt(s.ingresos) }}</span>
              </div>
              <div class="sede-progress-track">
                <div class="sede-progress-fill" :style="{ width: s.pct + '%' }"></div>
              </div>
              <span class="sede-pct">{{ s.pct }}%</span>
            </div>
          </div>
          <div v-else class="empty-state" style="padding: 40px 20px;">
            <p style="color: var(--fg-muted);">Sin datos de sedes</p>
          </div>
        </div>
      </div>

      <!-- Fila 4: Top Productos y Top Vendedores -->
      <div class="grid-2" style="margin-top: 16px;">
        <div class="card">
          <SectionTitle :icon="Trophy" title="Top 5 Productos por Ingreso" />
          <div v-if="data.top_productos?.length" class="ranking-list">
            <div v-for="(p, i) in data.top_productos" :key="i" class="ranking-row">
              <span class="rank-badge" :class="[`rank-${i < 3 ? i+1 : 'n'}`]">{{ i + 1 }}</span>
              <span class="ranking-name">{{ p.nombre }}</span>
              <div class="ranking-bar-wrap">
                <div class="ranking-bar-fill" :style="{ width: p.pct + '%' }"></div>
              </div>
              <span class="ranking-val">{{ _store.fmt(p.ingreso) }}</span>
            </div>
          </div>
          <p v-else style="padding: 20px; color: var(--fg-muted);">Carga el archivo de ventas.</p>
        </div>

        <!-- Top Vendedores / Laboratorios -->
        <div class="card">
          <!-- Si hay datos de vendedores, muéstralos -->
          <template v-if="data.top_vendedores?.length">
            <SectionTitle :icon="Users" title="Top 5 Vendedores por Ingreso" />
            <div class="ranking-list">
              <div v-for="(v, i) in data.top_vendedores" :key="i" class="ranking-row">
                <span class="rank-badge" :class="[`rank-${i < 3 ? i+1 : 'n'}`]">{{ i + 1 }}</span>
                <span class="ranking-name">{{ v.vendedor }}</span>
                <div class="ranking-bar-wrap">
                  <div class="ranking-bar-fill" :style="{ width: v.pct + '%' }"></div>
                </div>
                <span class="ranking-val">{{ _store.fmt(v.ingreso) }}</span>
              </div>
            </div>
          </template>
          <!-- Si no hay vendedores, muestra laboratorios -->
          <template v-else>
            <SectionTitle :icon="FlaskConical" title="Top 5 Laboratorios por Ingreso" />
            <div v-if="data.top_laboratorios?.length" class="ranking-list">
              <div v-for="(l, i) in data.top_laboratorios" :key="i" class="ranking-row">
                <span class="rank-badge" :class="[`rank-${i < 3 ? i+1 : 'n'}`]">{{ i + 1 }}</span>
                <span class="ranking-name">{{ l.laboratorio }}</span>
                <div class="ranking-bar-wrap">
                  <div class="ranking-bar-fill" :style="{ width: l.pct + '%' }"></div>
                </div>
                <span class="ranking-val">{{ _store.fmt(l.ingreso) }}</span>
              </div>
            </div>
            <p v-else style="padding: 20px; color: var(--fg-muted);">Sin datos de laboratorio disponibles.</p>
          </template>
        </div>
      </div>

    </template>

    <!-- Empty state -->
    <div v-else class="empty-state" style="padding: 80px 20px;">
      <LayoutDashboard size="52" color="var(--border)" />
      <h3 style="margin-top: 16px;">Sube tus archivos para activar el Centro de Comando</h3>
      <p style="color: var(--fg-muted);">Necesitas mínimo el archivo de <strong>Ventas</strong>. Con el de Inventario se activarán las alertas de stock.</p>
    </div>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import SectionTitle from '../components/ui/SectionTitle.vue'
import LineChart from '../components/charts/LineChart.vue'
import { LayoutDashboard, TrendingUp, TrendingDown, DollarSign, Gem, CreditCard, Package, Receipt, Activity, Siren, OctagonX, Timer, AlertTriangle, Warehouse, Store, Trophy, Users, RotateCcw, FlaskConical } from 'lucide-vue-next'
import { LineChart as LineChartIcon } from 'lucide-vue-next'

const _store  = useDashboardStore()
const data    = computed(() => _store.data.resumen)
const loading = computed(() => _store.loading.resumen)

function toIsoDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function parseIsoDate(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [y, m, d] = value.split('-').map(Number)
  const parsed = new Date(y, m - 1, d)
  if (
    parsed.getFullYear() !== y ||
    parsed.getMonth() !== m - 1 ||
    parsed.getDate() !== d
  ) return null
  return parsed
}

const now = new Date()
const todayIso = toIsoDate(now)
const yearStartIso = `${now.getFullYear()}-01-01`
const minAllowedDate = '2024-01-01'

const filters = ref({ fecha_ini: yearStartIso, fecha_fin: todayIso })

function normalizeFilters() {
  const minDate = parseIsoDate(minAllowedDate)
  const today = parseIsoDate(todayIso)
  let fin = parseIsoDate(filters.value.fecha_fin)
  let ini = parseIsoDate(filters.value.fecha_ini)

  if (!fin || fin < minDate || fin > today) fin = today
  if (!ini || ini < minDate) ini = new Date(fin.getFullYear(), 0, 1)
  if (ini < minDate) ini = minDate
  if (ini > today) ini = today
  if (ini > fin) fin = new Date(ini)

  filters.value.fecha_ini = toIsoDate(ini)
  filters.value.fecha_fin = toIsoDate(fin)

  return {
    fecha_ini: filters.value.fecha_ini,
    fecha_fin: filters.value.fecha_fin,
  }
}

function applyFilters() {
  _store.fetchResumen(normalizeFilters())
}

onMounted(() => {
  if (_store.status.ventas && !data.value) applyFilters()
})

const tendenciaCat  = computed(() => data.value?.tendencia?.map(d => d.fecha) || [])
const tendenciaData = computed(() => data.value?.tendencia?.map(d => d.ingreso) || [])

const displayPeriodDays = computed(() => {
  const inicio = parseIsoDate(data.value?.periodo?.inicio)
  const fin = parseIsoDate(data.value?.periodo?.fin)
  if (!inicio || !fin || inicio > fin) return data.value?.periodo?.dias || 0
  return Math.round((fin - inicio) / 86400000) + 1
})

const hayAlertas = computed(() => {
  const a = data.value?.alertas_inventario
  return a && (a.productos_sin_stock > 0 || a.productos_criticos_7d > 0 || a.productos_atencion_15d > 0 || a.capital_quieto > 0)
})

// Puntuación de salud del negocio (0-100)
const healthScore = computed(() => {
  if (!data.value) return '—'
  const a = data.value.alertas_inventario || {}
  const k = data.value.kpis
  let score = 100
  score -= Math.min(a.productos_sin_stock || 0, 20) * 2      // hasta -40 por quiebres
  score -= Math.min(a.productos_criticos_7d || 0, 10) * 1.5  // hasta -15 por críticos
  if (k.variacion_ing != null && k.variacion_ing < 0) score -= 10
  if (k.margen_pct != null && k.margen_pct < 10) score -= 10
  score = Math.max(0, Math.min(100, Math.round(score)))
  return score
})

const healthClass = computed(() => {
  const s = healthScore.value
  if (s === '—') return ''
  if (s >= 75) return 'health-good'
  if (s >= 45) return 'health-mid'
  return 'health-bad'
})

function formatFecha(f) {
  if (!f) return ''
  const parsed = parseIsoDate(f)
  if (!parsed) return f
  const [y, m, d] = f.split('-')
  const meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
  return `${d} ${meses[parseInt(m)-1]} ${y}`
}
</script>
