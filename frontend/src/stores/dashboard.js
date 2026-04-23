import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import axios from 'axios'

// Para producción, VITE_API_URL debe ser la URL de Render (ej. https://tu-api.onrender.com)
// En desarrollo local (vite dev), esto queda vacío y se usa el proxy de vite.config.js
axios.defaults.baseURL = import.meta.env.VITE_API_URL || ''
export const useDashboardStore = defineStore('dashboard', () => {
  // Estado de archivos cargados
  const status = reactive({ ventas: false, compras: false, inventario: false })
  const uploading = ref(false)
  const uploadError = ref(null)

  // Archivos pendientes de subida
  const files = reactive({ ventas: [], compras: [], inventario: null })

  // Datos de cada vista
  const data = reactive({
    resumen:       null,
    ventas:        null,
    rentabilidad:  null,
    inventario:    null,
    compras:       null,
    sedes:         null,
  })

  const loading = reactive({
    resumen: false, ventas: false, rentabilidad: false,
    inventario: false, compras: false, sedes: false,
  })

  // ── Helpers ──────────────────────────────────────────────
  function fmt(n) {
    if (n == null) return '—'
    const abs = Math.abs(n)
    if (abs >= 1_000_000) return `$${(n/1_000_000).toFixed(1)}M`
    if (abs >= 1_000)     return `$${(n/1_000).toFixed(0)}K`
    return `$${n.toFixed(0)}`
  }

  function fmtN(n) {
    if (n == null) return '—'
    return n.toLocaleString('es-CO')
  }

  // ── Upload ────────────────────────────────────────────────
  async function uploadFiles() {
    if (!files.ventas.length && !files.compras.length && !files.inventario) return
    uploading.value = true
    uploadError.value = null
    try {
      const fd = new FormData()
      files.ventas.forEach(f  => fd.append('ventas', f))
      files.compras.forEach(f => fd.append('compras', f))
      if (files.inventario)   fd.append('inventario', files.inventario)

      await axios.post('/api/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      await checkStatus()
    } catch (e) {
      uploadError.value = e.response?.data?.detail || 'Error al subir archivos'
    } finally {
      uploading.value = false
    }
  }

  async function checkStatus() {
    try {
      const { data: s } = await axios.get('/api/status')
      Object.assign(status, s)
    } catch {}
  }

  // ── Fetch data ────────────────────────────────────────────
  async function fetchResumen() {
    if (!status.ventas) return
    loading.resumen = true
    try {
      const { data: d } = await axios.get('/api/resumen')
      data.resumen = d
    } catch (e) { console.error(e) }
    finally { loading.resumen = false }
  }

  async function fetchVentas(params = {}) {
    if (!status.ventas) return
    loading.ventas = true
    try {
      const { data: d } = await axios.get('/api/ventas', { params })
      data.ventas = d
    } catch (e) { console.error(e) }
    finally { loading.ventas = false }
  }

  async function fetchRentabilidad() {
    if (!status.ventas || !status.inventario) return
    loading.rentabilidad = true
    try {
      const { data: d } = await axios.get('/api/rentabilidad')
      data.rentabilidad = d
    } catch (e) { console.error(e) }
    finally { loading.rentabilidad = false }
  }

  async function fetchInventario() {
    if (!status.inventario) return
    loading.inventario = true
    try {
      const { data: d } = await axios.get('/api/inventario')
      data.inventario = d
    } catch (e) { console.error(e) }
    finally { loading.inventario = false }
  }

  async function fetchCompras() {
    if (!status.ventas || !status.compras) return
    loading.compras = true
    try {
      const { data: d } = await axios.get('/api/compras')
      data.compras = d
    } catch (e) { console.error(e) }
    finally { loading.compras = false }
  }

  async function fetchSedes(params = {}) {
    if (!status.ventas) return
    loading.sedes = true
    try {
      const { data: d } = await axios.get('/api/sedes', { params })
      data.sedes = d
    } catch (e) { console.error(e) }
    finally { loading.sedes = false }
  }

  return {
    status, uploading, uploadError, files,
    data, loading,
    fmt, fmtN,
    uploadFiles, checkStatus,
    fetchResumen, fetchVentas, fetchRentabilidad,
    fetchInventario, fetchCompras, fetchSedes,
  }
})
