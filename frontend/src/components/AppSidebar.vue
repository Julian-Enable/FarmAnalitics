<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="sidebar-logo">
      <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 4px;">
        <Activity color="var(--accent)" size="28" />
        <h1 style="margin: 0; font-size: 1.5rem; letter-spacing: -0.5px;">Farma Analytics</h1>
      </div>
      <p style="margin: 0; font-size: 0.85rem; color: var(--text);">Análisis de POS Farmacéutico</p>
    </div>

    <!-- Navegación -->
    <nav class="sidebar-nav">
      <div class="nav-label">Análisis</div>
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

    <!-- Upload de archivos -->
    <div class="sidebar-upload">
      <div class="upload-title">
        <FileUp size="18" style="margin-right: 6px;" /> 
        Cargar archivos
      </div>

      <label class="upload-zone" :class="{ uploaded: ventasFiles.length }">
        <input type="file" multiple accept=".csv,.xlsx,.xls" @change="onVentas" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="ventasFiles.length" class="check">✓</span>
          <TrendingUp size="16" />
          <strong>Ventas</strong>
        </div>
        <span>{{ ventasFiles.length ? `${ventasFiles.length} archivo(s) listos` : 'CSV / Excel — múltiples OK' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: comprasFiles.length }">
        <input type="file" multiple accept=".csv,.xlsx,.xls" @change="onCompras" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="comprasFiles.length" class="check">✓</span>
          <Store size="16" />
          <strong>Compras</strong>
        </div>
        <span>{{ comprasFiles.length ? `${comprasFiles.length} archivo(s) listos` : 'CSV / Excel — múltiples OK' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: inventarioFile }">
        <input type="file" accept=".csv,.xlsx,.xls" @change="onInventario" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="inventarioFile" class="check">✓</span>
          <Database size="16" />
          <strong>Inventario</strong>
        </div>
        <span>{{ inventarioFile ? inventarioFile.name : 'Archivo maestro' }}</span>
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

      <!-- Estado -->
      <div style="margin-top:12px;">
        <div v-for="(label, key) in dataLabels" :key="key"
             style="display:flex;align-items:center;padding:3px 0;font-size:0.74rem;color:#6B7280;">
          <span class="status-dot" :class="store.status[key] ? 'on' : 'off'"></span>
          {{ label }}
        </div>
      </div>

      <div v-if="store.uploadError"
           style="margin-top:8px;padding:8px 10px;background:var(--red-bg);
                  border-radius:8px;font-size:0.74rem;color:var(--red); display:flex; gap: 6px; align-items: flex-start;">
        <AlertCircle size="14" style="flex-shrink:0; margin-top:2px;" />
        <span>{{ store.uploadError }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '../stores/dashboard'
import { LayoutDashboard, TrendingUp, DollarSign, AlertCircle, Scale, Store, FileUp, Database, FileSpreadsheet, Activity } from 'lucide-vue-next'

const store  = useDashboardStore()
const router = useRouter()

const ventasFiles    = ref([])
const comprasFiles   = ref([])
const inventarioFile = ref(null)

const hasFiles = computed(() =>
  ventasFiles.value.length > 0 || comprasFiles.value.length > 0 || inventarioFile.value
)

const navItems = [
  { to: '/',             icon: shallowRef(LayoutDashboard), label: 'Resumen General'    },
  { to: '/ventas',       icon: shallowRef(TrendingUp),      label: 'Análisis de Ventas' },
  { to: '/rentabilidad', icon: shallowRef(DollarSign),      label: 'Rentabilidad'        },
  { to: '/inventario',   icon: shallowRef(AlertCircle),     label: 'Alertas Inventario'  },
  { to: '/compras',      icon: shallowRef(Scale),           label: 'Compras vs Ventas'   },
  { to: '/sedes',        icon: shallowRef(Store),           label: 'Rendimiento Sedes'   },
]

const dataLabels = {
  ventas:     'Ventas cargadas',
  compras:    'Compras cargadas',
  inventario: 'Inventario cargado',
}

function onVentas(e)    { ventasFiles.value    = [...e.target.files] }
function onCompras(e)   { comprasFiles.value   = [...e.target.files] }
function onInventario(e){ inventarioFile.value = e.target.files[0] || null }

async function handleUpload() {
  store.files.ventas    = ventasFiles.value
  store.files.compras   = comprasFiles.value
  store.files.inventario = inventarioFile.value
  await store.uploadFiles()
  if (store.status.ventas) {
    await store.fetchResumen()
    router.push('/')
  }
}
</script>
