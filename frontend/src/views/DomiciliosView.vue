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

      <!-- Mapa de zonas de entrega -->
      <div class="card" style="margin-bottom:16px;">
        <div class="section-header-row">
          <SectionTitle :icon="MapPin" title="Zonas de entrega (por dirección)" />
          <div class="metric-toggle">
            <button :class="{ active: mapMode === 'burbujas' }" @click="setMapMode('burbujas')">Burbujas</button>
            <button :class="{ active: mapMode === 'calor' }" @click="setMapMode('calor')">Calor</button>
          </div>
        </div>
        <div v-if="data.kpis.pct_ubicado < 100" style="font-size:12px;color:var(--fg-muted);margin-bottom:8px;">
          {{ data.kpis.pct_ubicado }}% de los domicilios del periodo están ubicados en el mapa ({{ store.fmtN(data.kpis.ubicados_en_mapa) }} de {{ store.fmtN(data.kpis.total_domicilios) }}). El resto se ubica progresivamente en cada actualización.
        </div>
        <div class="map-wrap">
          <div ref="mapEl" class="map-container"></div>
          <div class="map-legend" v-if="mapMode === 'burbujas'">
            <div class="legend-title">Domicilios por zona</div>
            <div class="legend-row"><span class="legend-dot" style="background:#dc2626"></span> Muy alta</div>
            <div class="legend-row"><span class="legend-dot" style="background:#f97316"></span> Alta</div>
            <div class="legend-row"><span class="legend-dot" style="background:#eab308"></span> Media</div>
            <div class="legend-row"><span class="legend-dot" style="background:#3b82f6"></span> Baja</div>
            <div class="legend-hint">El círculo crece con la cantidad. Clic para ver cantidad y valor.</div>
          </div>
        </div>
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
const mapMode = ref('burbujas')
let map = null
let heatLayer = null
let markersLayer = null

function applyFilters() {
  const params = {}
  if (filters.value.fecha_ini) params.fecha_ini = filters.value.fecha_ini
  if (filters.value.fecha_fin) params.fecha_fin = filters.value.fecha_fin
  if (filters.value.sede && filters.value.sede !== 'Todas') params.sede = filters.value.sede
  store.fetchDomicilios(params)
}

function invalidateMapSize() {
  if (!map) return
  map.invalidateSize()
  setTimeout(() => map?.invalidateSize(), 150)
  setTimeout(() => map?.invalidateSize(), 500)
}

function initMap() {
  if (map || !mapEl.value) return
  map = L.map(mapEl.value, { scrollWheelZoom: false }).setView([4.655, -74.08], 12)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap', maxZoom: 19,
  }).addTo(map)
}

function clearMapLayers() {
  if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null }
  if (markersLayer) { map.removeLayer(markersLayer); markersLayer = null }
}

function colorFor(ratio) {
  if (ratio >= 0.5) return '#dc2626'   // Muy alta
  if (ratio >= 0.25) return '#f97316'  // Alta
  if (ratio >= 0.1) return '#eab308'   // Media
  return '#3b82f6'                     // Baja
}

function updateHeat() {
  if (!map) return
  const pts = (data.value?.mapa || [])
    .map(p => ({
      ...p,
      lat: Number(p.lat),
      lon: Number(p.lon),
      domicilios: Number(p.domicilios || 0),
      valor: Number(p.valor || 0),
    }))
    .filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon))
  clearMapLayers()
  invalidateMapSize()
  if (!pts.length) {
    map.setView([4.655, -74.08], 12)
    return
  }

  if (mapMode.value === 'calor' && L.heatLayer) {
    const maxC = Math.max(...pts.map(p => p.domicilios), 1)
    heatLayer = L.heatLayer(pts.map(p => [p.lat, p.lon, p.domicilios / maxC]), { radius: 22, blur: 18, maxZoom: 15 }).addTo(map)
  }
    // Burbujas proporcionales: tamaño y color crecen con la cantidad de domicilios.
    const maxC = Math.max(...pts.map(p => p.domicilios), 1)
    const top = [...pts].sort((a, b) => b.domicilios - a.domicilios).slice(0, 10)
    const topSet = new Set(top.map(p => `${p.lat},${p.lon}`))
    markersLayer = L.layerGroup()
    for (const p of pts) {
      const ratio = p.domicilios / maxC
      const radius = 6 + 22 * Math.sqrt(ratio)
      const m = L.circleMarker([p.lat, p.lon], {
        radius, color: '#ffffff', weight: 1.5, fillColor: colorFor(ratio), fillOpacity: mapMode.value === 'calor' ? 0.38 : 0.78,
      })
      m.bindPopup(
        `<div style="font-size:13px;"><b>${p.domicilios.toLocaleString('es-CO')} domicilios</b><br>` +
        `$${Math.round(p.valor).toLocaleString('es-CO')}</div>`
      )
      if (mapMode.value !== 'calor' && topSet.has(`${p.lat},${p.lon}`)) {
        m.bindTooltip(p.domicilios.toLocaleString('es-CO'), { permanent: true, direction: 'center', className: 'zone-label' })
      }
      m.addTo(markersLayer)
    }
    markersLayer.addTo(map)

  const bounds = L.latLngBounds(pts.map(p => [p.lat, p.lon]))
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 })
  invalidateMapSize()
}

function setMapMode(mode) {
  mapMode.value = mode
  updateHeat()
}

const mensCat = computed(() => (data.value?.por_mensajero || []).slice(0, 12).map(m => m.Mensajero))
const mensData = computed(() => (data.value?.por_mensajero || []).slice(0, 12).map(m => mMetric.value === 'valor' ? Math.round(m.valor) : m.domicilios))
const estadoCat = computed(() => (data.value?.por_estado || []).map(e => e.estado || e.Estado))
const estadoData = computed(() => (data.value?.por_estado || []).map(e => e.domicilios))
const tendCat = computed(() => (data.value?.tendencia || []).map(t => t.fecha))
const tendData = computed(() => (data.value?.tendencia || []).map(t => t.domicilios))

async function renderMap() {
  await heatReady
  await nextTick()
  initMap()
  invalidateMapSize()
  updateHeat()
}

watch(() => data.value?.mapa, () => { renderMap() }, { flush: 'post' })

onMounted(async () => {
  if (store.status.domicilios && !data.value) applyFilters()
  await renderMap()
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
.map-wrap {
  position: relative;
}
.map-container {
  width: 100%;
  height: 460px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
}
.map-legend {
  position: absolute;
  bottom: 14px;
  right: 14px;
  z-index: 1000;
  background: var(--card, #fff);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 11px;
  color: var(--fg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-width: 180px;
}
.legend-title {
  font-weight: 700;
  margin-bottom: 4px;
}
.legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 1px 0;
}
.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
  border: 1px solid #fff;
}
.legend-hint {
  margin-top: 6px;
  color: var(--fg-muted);
  font-size: 10px;
  line-height: 1.3;
}
:deep(.zone-label) {
  background: transparent;
  border: none;
  box-shadow: none;
  color: #fff;
  font-weight: 700;
  font-size: 11px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
}
:deep(.zone-label::before) {
  display: none;
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
