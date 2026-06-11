<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <Bike size="32" color="var(--accent)" />
        <h2 style="margin:0;">Domicilios</h2>
      </div>
      <p style="margin-top:8px;">Domicilios por mensajero, valor entregado, tarifa de servicio y mapa de calor por zona de entrega.</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Qué te muestra esta página?</strong></p>
      <ul style="margin-left:20px;margin-top:8px;">
        <li><strong>Valor movido:</strong> total de las facturas que se entregaron a domicilio.</li>
        <li><strong>Tarifa de servicio:</strong> lo cobrado por el servicio de domicilio en sí (líneas "SERVICIO DOMICILIO / POLÍGONO").</li>
        <li><strong>Por mensajero:</strong> cuántos domicilios y cuánto valor llevó cada domiciliario, y su % de entregas completadas.</li>
        <li><strong>Mapa de calor:</strong> zonas con más domicilios según la dirección de entrega geocodificada. Las direcciones que no se pudieron ubicar no aparecen en el mapa pero sí en la tabla.</li>
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

    <div v-if="store.errors.domicilios" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.domicilios }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 4" :key="i" class="card skeleton" style="height:100px;"></div>
    </div>

    <template v-else-if="data">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom:16px;">
        <KpiCard :icon="Bike" label="Domicilios" :value="store.fmtN(data.kpis.total_domicilios)" />
        <KpiCard :icon="CheckCircle2" label="% Entregados" :value="data.kpis.pct_entregado + '%'" />
        <KpiCard :icon="DollarSign" label="Valor Movido" :value="store.fmt(data.kpis.valor_movido)" />
        <KpiCard :icon="Receipt" label="Tarifa Servicio" :value="store.fmt(data.kpis.tarifa_servicio)" />
        <KpiCard :icon="Users" label="Mensajeros" :value="store.fmtN(data.kpis.n_mensajeros)" />
        <KpiCard :icon="Wallet" label="Ticket Promedio" :value="store.fmt(data.kpis.ticket_promedio)" />
        <KpiCard :icon="Package" label="Servicios Domicilio" :value="store.fmtN(data.kpis.n_servicios_domicilio)" />
        <KpiCard :icon="MapPin" label="Ubicados en Mapa" :value="data.kpis.pct_ubicado + '%'" />
      </div>

      <!-- Mapa de calor -->
      <div class="card" style="margin-bottom:16px;">
        <SectionTitle :icon="MapPin" title="Mapa de calor de entregas (por dirección)" />
        <div v-if="data.kpis.pct_ubicado < 100" style="font-size:12px;color:var(--fg-muted);margin-bottom:8px;">
          {{ data.kpis.pct_ubicado }}% de los domicilios del periodo están geocodificados ({{ store.fmtN(data.kpis.ubicados_en_mapa) }} de {{ store.fmtN(data.kpis.total_domicilios) }}). El resto se geocodifica progresivamente en cada actualización.
        </div>
        <div ref="mapEl" class="map-container"></div>
      </div>

      <div class="grid-2">
        <!-- Por mensajero -->
        <div class="card">
          <div class="section-header-row">
            <SectionTitle :icon="Users" title="Domicilios por domiciliario" />
            <div class="metric-toggle">
              <button :class="{ active: mMetric === 'domicilios' }" @click="mMetric = 'domicilios'">Cantidad</button>
              <button :class="{ active: mMetric === 'valor' }" @click="mMetric = 'valor'">Valor</button>
            </div>
          </div>
          <BarChart v-if="mensCat.length" :horizontal="true" :formatTooltip="mMetric === 'valor' ? 'currency' : ''"
                    :categories="mensCat" :series="[{ name: mMetric === 'valor' ? 'Valor' : 'Domicilios', data: mensData }]" />
        </div>

        <!-- Por estado -->
        <div class="card">
          <SectionTitle :icon="Activity" title="Estado de las entregas" />
          <DonutChart v-if="estadoCat.length" :labels="estadoCat" :series="estadoData" />
        </div>

        <!-- Tendencia -->
        <div class="card" style="grid-column: span 2;">
          <SectionTitle :icon="TrendingUp" title="Tendencia de domicilios" />
          <LineChart v-if="tendCat.length" :categories="tendCat" :series="[{ name: 'Domicilios', data: tendData }]" />
        </div>

        <!-- Tabla mensajeros -->
        <div class="card" style="grid-column: span 2;">
          <div class="section-header-row">
            <SectionTitle :icon="ClipboardList" title="Detalle por domiciliario" />
            <button class="export-btn" @click="exportMensajeros"><Download size="16" /> Exportar CSV</button>
          </div>
          <div style="overflow-x:auto;">
            <table class="data-table">
              <thead>
                <tr><th>Domiciliario</th><th>Domicilios</th><th>Entregados</th><th>% Entregado</th><th>Valor</th></tr>
              </thead>
              <tbody>
                <tr v-for="m in data.por_mensajero" :key="m.Mensajero">
                  <td style="font-weight:600;">{{ m.Mensajero }}</td>
                  <td>{{ store.fmtN(m.domicilios) }}</td>
                  <td>{{ store.fmtN(m.entregados) }}</td>
                  <td>
                    <span class="badge" :class="m.pct_entregado >= 95 ? 'badge-green' : (m.pct_entregado >= 85 ? 'badge-amber' : 'badge-red')">{{ m.pct_entregado }}%</span>
                  </td>
                  <td style="font-weight:600;color:var(--green);">{{ store.fmt(m.valor) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><Bike size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Se requieren datos de domicilios. Actualiza la información desde tu PC para descargarlos.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import BarChart from '../components/charts/BarChart.vue'
import DonutChart from '../components/charts/DonutChart.vue'
import LineChart from '../components/charts/LineChart.vue'
import { exportToCSV } from '../utils/export'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { Bike, CheckCircle2, DollarSign, Receipt, Users, Wallet, Package, MapPin, Activity, TrendingUp, ClipboardList, Download } from 'lucide-vue-next'

// leaflet.heat (0.2.0) es un IIFE que referencia la global window.L, así que se
// expone L y se importa de forma dinámica antes de usar L.heatLayer.
if (typeof window !== 'undefined') window.L = L
const heatReady = import('leaflet.heat').catch(() => {})

const store = useDashboardStore()
const data = computed(() => store.data.domicilios)
const loading = computed(() => store.loading.domicilios)
const filters = ref({ fecha_ini: '', fecha_fin: '', sede: 'Todas' })
const mMetric = ref('domicilios')

const mapEl = ref(null)
let map = null
let heatLayer = null

function applyFilters() {
  const params = {}
  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  if (filters.value.sede && filters.value.sede !== 'Todas') params.sede = filters.value.sede
  store.fetchDomicilios(params)
}

function initMap() {
  if (map || !mapEl.value) return
  map = L.map(mapEl.value, { scrollWheelZoom: false }).setView([4.655, -74.08], 12)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap', maxZoom: 19,
  }).addTo(map)
}

function updateHeat() {
  if (!map || !L.heatLayer) return
  const pts = (data.value?.mapa || [])
  if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null }
  if (!pts.length) return
  const maxC = Math.max(...pts.map(p => p.domicilios), 1)
  const heatPoints = pts.map(p => [p.lat, p.lon, p.domicilios / maxC])
  heatLayer = L.heatLayer(heatPoints, { radius: 22, blur: 18, maxZoom: 15 }).addTo(map)
  const bounds = L.latLngBounds(pts.map(p => [p.lat, p.lon]))
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 })
}

const mensCat = computed(() => (data.value?.por_mensajero || []).slice(0, 12).map(m => m.Mensajero))
const mensData = computed(() => (data.value?.por_mensajero || []).slice(0, 12).map(m => mMetric.value === 'valor' ? Math.round(m.valor) : m.domicilios))
const estadoCat = computed(() => (data.value?.por_estado || []).map(e => e.estado || e.Estado))
const estadoData = computed(() => (data.value?.por_estado || []).map(e => e.domicilios))
const tendCat = computed(() => (data.value?.tendencia || []).map(t => t.fecha))
const tendData = computed(() => (data.value?.tendencia || []).map(t => t.domicilios))

watch(() => data.value?.mapa, () => { nextTick(() => { initMap(); updateHeat(); if (map) setTimeout(() => map.invalidateSize(), 100) }) })

onMounted(async () => {
  if (store.status.domicilios && !data.value) applyFilters()
  await heatReady
  await nextTick()
  initMap()
  updateHeat()
})

onBeforeUnmount(() => { if (map) { map.remove(); map = null } })

function exportMensajeros() {
  const cols = [
    { key: 'Mensajero', label: 'Domiciliario' },
    { key: 'domicilios', label: 'Domicilios' },
    { key: 'entregados', label: 'Entregados' },
    { key: 'pct_entregado', label: '% Entregado' },
    { key: 'valor', label: 'Valor' },
  ]
  exportToCSV(data.value?.por_mensajero || [], cols, 'Domicilios_por_Mensajero')
}
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 460px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
}
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
