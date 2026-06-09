<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="sidebar-logo">
      <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 4px;">
        <Activity color="var(--accent)" size="28" />
        <h1 style="margin: 0; font-size: 1.5rem; letter-spacing: -0.5px;">Farma Analytics</h1>
      </div>
      <p style="margin: 0; font-size: 0.85rem; color: var(--text);">Analisis de POS Farmaceutico</p>
    </div>

    <!-- Navegacion -->
    <nav class="sidebar-nav">
      <div class="nav-label">Analisis</div>
      <router-link
        v-for="item in navItems" :key="item.to"
        :to="item.to" custom v-slot="{ isActive, navigate }"
      >
        <button class="nav-link" :class="{ active: isActive }" @click="navigate">
          <component :is="item.icon" class="nav-icon-lucide" />
          {{ item.label }}
        </button>
      </router-link>
    </nav>

    <!-- Estado de Base de Datos -->
    <div v-if="store.status.db_connected || store.historicalStatus?.available" class="sidebar-upload" style="background-color: var(--card-alt); border: 1px solid rgba(16, 185, 129, 0.2);">
      <div class="upload-title" style="color: var(--green); display:flex; align-items:center; gap: 6px;">
        <Database size="18" />
        {{ store.status.db_connected ? 'Conexion en tiempo real' : 'Datos historicos cargados' }}
      </div>
      <div style="font-size: 0.8rem; color: var(--text); margin-top: 8px;">
        <template v-if="store.status.db_connected">
          Conectado a Azure SQL Server. <br/>(Usuario: SPD_FARMAZION)
        </template>
        <template v-else>
          Usando historico local en Railway. SQL en vivo bloqueado por firewall de Azure.
        </template>
      </div>
      <div style="font-size: 0.75rem; color: var(--green); margin-top: 6px; display: flex; align-items: center; gap: 4px;">
        <span class="status-dot on"></span>
        {{ store.status.db_connected ? 'Lectura segura activa' : 'Historico disponible' }}
      </div>
      <div v-if="lastHistoricalUpdate" style="font-size: 0.72rem; color: var(--fg-muted); margin-top: 6px;">
        Ultima actualizacion: {{ lastHistoricalUpdate }}
      </div>

      <button
        class="btn-upload"
        style="margin-top: 12px;"
        :disabled="store.refreshingLive || !store.status.db_connected"
        @click="handleLiveRefresh"
      >
        <span style="display:flex; align-items:center; justify-content:center; gap: 6px;">
          <RefreshCw size="15" :class="{ spinning: store.refreshingLive }" />
          {{ liveRefreshLabel }}
        </span>
      </button>

      <button
        class="btn-secondary"
        style="margin-top: 8px;"
        :disabled="store.exporting"
        @click="store.exportFullReport"
      >
        <Download size="15" />
        {{ store.exporting ? 'Exportando...' : 'Exportar reporte' }}
      </button>
    </div>

    <!-- Upload de archivos (Oculto si hay BD conectada) -->
    <div v-else class="sidebar-upload">
      <div class="upload-title">
        <FileUp size="18" style="margin-right: 6px;" />
        Cargar archivos
      </div>

      <label class="upload-zone" :class="{ uploaded: ventasFiles.length }">
        <input type="file" multiple accept=".csv,.xlsx,.xls" @change="onVentas" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="ventasFiles.length" class="check">OK</span>
          <TrendingUp size="16" />
          <strong>Ventas</strong>
        </div>
        <span>{{ ventasFiles.length ? `${ventasFiles.length} archivo(s) listos` : 'CSV / Excel - multiples OK' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: comprasFiles.length }">
        <input type="file" multiple accept=".csv,.xlsx,.xls" @change="onCompras" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="comprasFiles.length" class="check">OK</span>
          <Store size="16" />
          <strong>Compras</strong>
        </div>
        <span>{{ comprasFiles.length ? `${comprasFiles.length} archivo(s) listos` : 'CSV / Excel - multiples OK' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: inventarioFile }">
        <input type="file" accept=".csv,.xlsx,.xls" @change="onInventario" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="inventarioFile" class="check">OK</span>
          <Database size="16" />
          <strong>Inventario</strong>
        </div>
        <span>{{ inventarioFile ? inventarioFile.name : 'Archivo maestro' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: notasCreditoFile }">
        <input type="file" accept=".csv,.xlsx,.xls" @change="onNotasCredito" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="notasCreditoFile" class="check">OK</span>
          <RotateCcw size="16" />
          <strong>Notas Credito</strong>
        </div>
        <span>{{ notasCreditoFile ? notasCreditoFile.name : 'CSV / Excel - opcional' }}</span>
      </label>

      <button
        class="btn-upload"
        :disabled="store.uploading || !hasFiles"
        @click="handleUpload"
      >
        <span v-if="store.uploading">Procesando...</span>
        <span v-else style="display:flex; align-items:center; justify-content:center; gap: 6px;">
          <Activity size="16" /> Analizar datos
        </span>
      </button>

      <button
        class="btn-secondary"
        :disabled="store.exporting || !hasLoadedData"
        @click="store.exportFullReport"
      >
        <Download size="15" />
        {{ store.exporting ? 'Exportando...' : 'Exportar reporte' }}
      </button>

      <button
        class="btn-danger"
        :disabled="!hasLoadedData && !hasFiles"
        @click="handleReset"
      >
        <Trash2 size="15" /> Limpiar datos
      </button>

      <div style="margin-top:12px;">
        <div v-for="(label, key) in dataLabels" :key="key"
             style="display:flex;align-items:center;padding:3px 0;font-size:0.74rem;color:#6B7280;">
          <span class="status-dot" :class="store.status[key] ? 'on' : 'off'"></span>
          {{ label }}
        </div>
      </div>

      <div v-if="store.uploadError"
           style="margin-top:8px;padding:8px 10px;background:#fff1f2;
                  border-radius:8px;font-size:0.74rem;color:var(--red); display:flex; gap: 6px; align-items: flex-start;">
        <AlertCircle size="14" style="flex-shrink:0; margin-top:2px;" />
        <span>{{ store.uploadError }}</span>
      </div>

      <div v-if="store.lastError && !store.uploadError"
           style="margin-top:8px;padding:8px 10px;background:#fff1f2;
                  border-radius:8px;font-size:0.74rem;color:#be123c; display:flex; gap: 6px; align-items: flex-start;">
        <AlertCircle size="14" style="flex-shrink:0; margin-top:2px;" />
        <span>{{ store.lastError }}</span>
      </div>

      <div v-if="store.uploadDiagnostic" style="margin-top:10px;">
        <div v-for="diag in diagnosticItems" :key="diag.tipo"
             style="font-size:0.72rem;padding:6px 8px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;background:white;">
          <div style="display:flex;justify-content:space-between;gap:8px;font-weight:700;">
            <span>{{ diagnosticLabels[diag.tipo] || diag.tipo }}</span>
            <span :style="{ color: diag.ok ? 'var(--green)' : 'var(--red)' }">
              {{ diag.ok ? 'OK' : 'Faltan columnas' }}
            </span>
          </div>
          <div style="color:var(--fg-muted);margin-top:2px;">{{ store.fmtN(diag.filas) }} filas - {{ diag.columnas.length }} columnas</div>
          <div v-if="diag.faltantes.length" style="color:var(--red);margin-top:2px;">
            Faltan: {{ diag.faltantes.join(', ') }}
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '../stores/dashboard'
import { LayoutDashboard, TrendingUp, DollarSign, AlertCircle, Scale, Store, FileUp, Database, Activity, Download, Trash2, RotateCcw, Target, RefreshCw } from 'lucide-vue-next'

const store  = useDashboardStore()
const router = useRouter()

const ventasFiles    = ref([])
const comprasFiles   = ref([])
const inventarioFile = ref(null)
const notasCreditoFile = ref(null)

const hasFiles = computed(() =>
  ventasFiles.value.length > 0 || comprasFiles.value.length > 0 || inventarioFile.value || notasCreditoFile.value
)
const hasLoadedData = computed(() =>
  store.status.ventas || store.status.compras || store.status.inventario || store.status.notas_credito
)
const diagnosticItems = computed(() =>
  store.uploadDiagnostic ? Object.values(store.uploadDiagnostic) : []
)
const lastHistoricalUpdate = computed(() =>
  store.formatDateTime(store.historicalStatus?.datasets?.ventas?.max)
)
const liveRefreshLabel = computed(() => {
  if (store.refreshingLive) return 'Actualizando...'
  if (!store.status.db_connected) return 'SQL en vivo bloqueado'
  return 'Actualizar informacion en vivo'
})

const navItems = [
  { to: '/',             icon: shallowRef(LayoutDashboard), label: 'Resumen General'    },
  { to: '/ventas',       icon: shallowRef(TrendingUp),      label: 'Analisis de Ventas' },
  { to: '/rentabilidad', icon: shallowRef(DollarSign),      label: 'Rentabilidad'        },
  { to: '/inventario',   icon: shallowRef(AlertCircle),     label: 'Alertas Inventario'  },
  { to: '/compras',      icon: shallowRef(Scale),           label: 'Compras vs Ventas'   },
  { to: '/sedes',        icon: shallowRef(Store),           label: 'Rendimiento Sedes'   },
  { to: '/devoluciones', icon: shallowRef(RotateCcw),       label: 'Devoluciones'        },
  { to: '/metas',        icon: shallowRef(Target),          label: 'Proyeccion y Metas'  },
]

const dataLabels = {
  ventas:       'Ventas cargadas',
  compras:      'Compras cargadas',
  inventario:   'Inventario cargado',
  notas_credito: 'Notas credito cargadas',
}
const diagnosticLabels = {
  ventas: 'Ventas',
  compras: 'Compras',
  inventario: 'Inventario',
}

function onVentas(e)       { ventasFiles.value      = [...e.target.files] }
function onCompras(e)      { comprasFiles.value     = [...e.target.files] }
function onInventario(e)   { inventarioFile.value   = e.target.files[0] || null }
function onNotasCredito(e) { notasCreditoFile.value = e.target.files[0] || null }

async function handleUpload() {
  store.files.ventas        = ventasFiles.value
  store.files.compras       = comprasFiles.value
  store.files.inventario    = inventarioFile.value
  store.files.notas_credito = notasCreditoFile.value
  await store.uploadFiles()
  if (store.status.ventas) {
    await store.fetchResumen()
    router.push('/')
  }
}

async function handleReset() {
  ventasFiles.value      = []
  comprasFiles.value     = []
  inventarioFile.value   = null
  notasCreditoFile.value = null
  await store.resetSession()
  router.push('/')
}

async function handleLiveRefresh() {
  await store.refreshLiveInformation()
  router.push('/')
}
</script>

<style scoped>
.spinning {
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
