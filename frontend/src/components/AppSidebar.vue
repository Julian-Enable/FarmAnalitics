<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="sidebar-logo">
      <h1>💊 Dashboard Farma</h1>
      <p>Análisis de POS Farmacéutico</p>
    </div>

    <!-- Navegación -->
    <nav class="sidebar-nav">
      <div class="nav-label">Análisis</div>
      <router-link
        v-for="item in navItems" :key="item.to"
        :to="item.to" custom v-slot="{ isActive, navigate }"
      >
        <button class="nav-link" :class="{ active: isActive }" @click="navigate">
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </button>
      </router-link>
    </nav>

    <!-- Upload de archivos -->
    <div class="sidebar-upload">
      <div class="upload-title">📁 Cargar archivos</div>

      <label class="upload-zone" :class="{ uploaded: ventasFiles.length }">
        <input type="file" multiple accept=".csv,.xlsx,.xls" @change="onVentas" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="ventasFiles.length" class="check">✓</span>
          <strong>📈 Ventas</strong>
        </div>
        <span>{{ ventasFiles.length ? `${ventasFiles.length} archivo(s) listos` : 'CSV / Excel — múltiples OK' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: comprasFiles.length }">
        <input type="file" multiple accept=".csv,.xlsx,.xls" @change="onCompras" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="comprasFiles.length" class="check">✓</span>
          <strong>🛒 Compras</strong>
        </div>
        <span>{{ comprasFiles.length ? `${comprasFiles.length} archivo(s) listos` : 'CSV / Excel — múltiples OK' }}</span>
      </label>

      <label class="upload-zone" :class="{ uploaded: inventarioFile }">
        <input type="file" accept=".csv,.xlsx,.xls" @change="onInventario" />
        <div style="display:flex;align-items:center;gap:6px;">
          <span v-if="inventarioFile" class="check">✓</span>
          <strong>📦 Inventario</strong>
        </div>
        <span>{{ inventarioFile ? inventarioFile.name : 'Archivo maestro' }}</span>
      </label>

      <button
        class="btn-upload"
        :disabled="store.uploading || !hasFiles"
        @click="handleUpload"
      >
        {{ store.uploading ? '⏳ Procesando...' : '🚀 Analizar datos' }}
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
           style="margin-top:8px;padding:8px 10px;background:#FEE2E2;
                  border-radius:8px;font-size:0.74rem;color:#991B1B;">
        ⚠️ {{ store.uploadError }}
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '../stores/dashboard'

const store  = useDashboardStore()
const router = useRouter()

const ventasFiles    = ref([])
const comprasFiles   = ref([])
const inventarioFile = ref(null)

const hasFiles = computed(() =>
  ventasFiles.value.length > 0 || comprasFiles.value.length > 0 || inventarioFile.value
)

const navItems = [
  { to: '/',             icon: '🏠', label: 'Resumen General'    },
  { to: '/ventas',       icon: '📈', label: 'Análisis de Ventas' },
  { to: '/rentabilidad', icon: '💰', label: 'Rentabilidad'        },
  { to: '/inventario',   icon: '🚨', label: 'Alertas Inventario'  },
  { to: '/compras',      icon: '⚖️', label: 'Compras vs Ventas'   },
  { to: '/sedes',        icon: '🏪', label: 'Rendimiento Sedes'   },
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
