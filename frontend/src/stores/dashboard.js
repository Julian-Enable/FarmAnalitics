import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import axios from 'axios'
import { exportWorkbookAsExcel } from '../utils/export'

const sessionId = localStorage.getItem('farm_session_id') || crypto.randomUUID()
localStorage.setItem('farm_session_id', sessionId)

const productionApiUrl = 'https://farmanalitics-production.up.railway.app'
axios.defaults.baseURL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? productionApiUrl : '')
axios.interceptors.request.use(config => {
  config.headers['x-session-id'] = sessionId
  return config
})

export const useDashboardStore = defineStore('dashboard', () => {
  const status = reactive({ ventas: false, compras: false, inventario: false, notas_credito: false, metas: false })
  const uploading = ref(false)
  const exporting = ref(false)
  const refreshingLive = ref(false)
  const uploadError = ref(null)
  const uploadDiagnostic = ref(null)
  const lastError = ref(null)
  const historicalStatus = ref(null)

  const settings = reactive({
    inv_min_dias: 25,
    inv_max_dias: 40,
    quieto_dias: 60,
  })

  const files = reactive({ ventas: [], compras: [], inventario: null, notas_credito: null })

  const data = reactive({
    resumen: null,
    ventas: null,
    rentabilidad: null,
    inventario: null,
    compras: null,
    sedes: null,
    devoluciones: null,
    metas: null,
  })

  const loading = reactive({
    resumen: false,
    ventas: false,
    rentabilidad: false,
    inventario: false,
    compras: false,
    sedes: false,
    devoluciones: false,
    metas: false,
  })

  const errors = reactive({
    resumen: null,
    ventas: null,
    rentabilidad: null,
    inventario: null,
    compras: null,
    sedes: null,
    devoluciones: null,
    metas: null,
  })

  function fmt(n) {
    if (n == null) return '—'
    const abs = Math.abs(n)
    if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
    if (abs >= 1_000) return `$${(n / 1_000).toFixed(0)}K`
    return `$${Number(n).toFixed(0)}`
  }

  function fmtN(n) {
    if (n == null) return '—'
    return Number(n).toLocaleString('es-CO')
  }

  function errorMessage(e, fallback = 'No se pudo completar la operación') {
    return e.response?.data?.detail || e.message || fallback
  }

  function setModuleError(module, e, fallback) {
    const message = errorMessage(e, fallback)
    errors[module] = message
    lastError.value = message
  }

  function clearModuleError(module) {
    errors[module] = null
    lastError.value = null
  }

  function clearData() {
    Object.keys(data).forEach(key => { data[key] = null })
  }

  function formatDateTime(value) {
    if (!value) return null
    const date = new Date(String(value).replace(' ', 'T'))
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString('es-CO', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  function inventoryParams(extra = {}) {
    return {
      inv_min_dias: settings.inv_min_dias,
      inv_max_dias: settings.inv_max_dias,
      quieto_dias: settings.quieto_dias,
      ...extra,
    }
  }

  async function uploadFiles() {
    if (!files.ventas.length && !files.compras.length && !files.inventario && !files.notas_credito) return
    uploading.value = true
    uploadError.value = null
    uploadDiagnostic.value = null
    lastError.value = null

    try {
      const fd = new FormData()
      files.ventas.forEach(f => fd.append('ventas', f))
      files.compras.forEach(f => fd.append('compras', f))
      if (files.inventario) fd.append('inventario', files.inventario)
      if (files.notas_credito) fd.append('notas_credito', files.notas_credito)

      const { data: result } = await axios.post('/api/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      uploadDiagnostic.value = result.diagnostico || null
      clearData()
      await checkStatus()
    } catch (e) {
      uploadError.value = errorMessage(e, 'Error al subir archivos')
      lastError.value = uploadError.value
    } finally {
      uploading.value = false
    }
  }

  async function checkStatus() {
    try {
      const { data: s } = await axios.get('/api/status')
      Object.assign(status, s)
      historicalStatus.value = s.historical || historicalStatus.value
    } catch (e) {
      lastError.value = errorMessage(e, 'No se pudo consultar el estado de la sesión')
    }
  }

  async function fetchHistoricalStatus() {
    try {
      const { data: s } = await axios.get('/api/historico/status')
      historicalStatus.value = s
      return s
    } catch (e) {
      lastError.value = errorMessage(e, 'No se pudo consultar el historico local')
      return null
    }
  }

  async function refreshLiveInformation() {
    refreshingLive.value = true
    lastError.value = null
    try {
      const { data: result } = await axios.post('/api/historico/actualizar')
      historicalStatus.value = result.status || historicalStatus.value
      clearData()
      await checkStatus()
      if (status.ventas) await fetchResumen()
      return result
    } catch (e) {
      lastError.value = errorMessage(e, 'No se pudo actualizar la informacion en vivo')
      throw e
    } finally {
      refreshingLive.value = false
    }
  }

  async function resetSession() {
    try {
      await axios.delete('/api/reset')
      Object.assign(status, { ventas: false, compras: false, inventario: false, notas_credito: false })
      Object.assign(files, { ventas: [], compras: [], inventario: null, notas_credito: null })
      Object.keys(errors).forEach(key => { errors[key] = null })
      uploadDiagnostic.value = null
      uploadError.value = null
      lastError.value = null
      clearData()
      await checkStatus()
    } catch (e) {
      lastError.value = errorMessage(e, 'No se pudo limpiar la sesión')
    }
  }

  async function fetchResumen(params = {}) {
    if (!status.ventas) return
    loading.resumen = true
    clearModuleError('resumen')
    try {
      const { data: d } = await axios.get('/api/resumen', { params })
      data.resumen = d
    } catch (e) { setModuleError('resumen', e, 'No se pudo cargar el resumen') }
    finally { loading.resumen = false }
  }

  async function fetchVentas(params = {}) {
    if (!status.ventas) return
    loading.ventas = true
    clearModuleError('ventas')
    try {
      const { data: d } = await axios.get('/api/ventas', { params })
      data.ventas = d
    } catch (e) { setModuleError('ventas', e, 'No se pudo cargar ventas') }
    finally { loading.ventas = false }
  }

  async function fetchRentabilidad(params = {}) {
    if (!status.ventas || !status.inventario) return
    loading.rentabilidad = true
    clearModuleError('rentabilidad')
    try {
      const { data: d } = await axios.get('/api/rentabilidad', { params })
      data.rentabilidad = d
    } catch (e) { setModuleError('rentabilidad', e, 'No se pudo cargar rentabilidad') }
    finally { loading.rentabilidad = false }
  }

  async function fetchInventario(params = {}) {
    if (!status.inventario) return
    loading.inventario = true
    clearModuleError('inventario')
    try {
      const { data: d } = await axios.get('/api/inventario', { params: inventoryParams(params) })
      data.inventario = d
    } catch (e) { setModuleError('inventario', e, 'No se pudo cargar inventario') }
    finally { loading.inventario = false }
  }

  async function fetchCompras(params = {}) {
    if (!status.ventas || !status.compras || !status.inventario) return
    loading.compras = true
    clearModuleError('compras')
    try {
      const { data: d } = await axios.get('/api/compras', { params: inventoryParams(params) })
      data.compras = d
    } catch (e) { setModuleError('compras', e, 'No se pudo cargar compras') }
    finally { loading.compras = false }
  }

  async function fetchSedes(params = {}) {
    if (!status.ventas) return
    loading.sedes = true
    clearModuleError('sedes')
    try {
      const { data: d } = await axios.get('/api/sedes', { params })
      data.sedes = d
    } catch (e) { setModuleError('sedes', e, 'No se pudo cargar sedes') }
    finally { loading.sedes = false }
  }

  async function fetchDevoluciones(params = {}) {
    if (!status.notas_credito) return
    loading.devoluciones = true
    clearModuleError('devoluciones')
    try {
      const { data: d } = await axios.get('/api/notas-credito', { params })
      data.devoluciones = d
    } catch (e) { setModuleError('devoluciones', e, 'No se pudo cargar devoluciones') }
    finally { loading.devoluciones = false }
  }

  async function fetchMetas(agresividad = 'normal', fecha_ini = null, fecha_fin = null) {
    loading.metas = true
    clearModuleError('metas')
    try {
      const { data: d } = await axios.get('/api/metas', { 
        params: { agresividad, fecha_ini, fecha_fin } 
      })
      data.metas = d
    } catch (e) { setModuleError('metas', e, 'No se pudo calcular las metas') }
    finally { loading.metas = false }
  }

  async function exportFullReport() {
    exporting.value = true
    lastError.value = null
    try {
      if (status.ventas && !data.resumen) await fetchResumen()
      if (status.ventas && !data.ventas) await fetchVentas()
      if (status.ventas && status.inventario && !data.rentabilidad) await fetchRentabilidad()
      if (status.inventario && !data.inventario) await fetchInventario()
      if (status.ventas && status.compras && status.inventario && !data.compras) await fetchCompras()
      if (status.ventas && !data.sedes) await fetchSedes()
      if (status.notas_credito && !data.devoluciones) await fetchDevoluciones()

      exportWorkbookAsExcel([
        {
          name: 'Ventas detalle',
          data: data.ventas?.detalle_productos || [],
          columns: [
            { key: 'Referencia', label: 'Referencia' },
            { key: 'Descripcion', label: 'Descripcion' },
            { key: 'Laboratorio', label: 'Laboratorio' },
            { key: 'unidades', label: 'Unidades' },
            { key: 'ingreso', label: 'Ingreso' },
          ],
        },
        {
          name: 'Vendedores',
          data: data.ventas?.vendedores || [],
          columns: [
            { key: 'vendedor', label: 'Vendedor' },
            { key: 'unidades', label: 'Unidades' },
            { key: 'ingresos', label: 'Ingresos' },
            { key: 'facturas', label: 'Transacciones' },
          ],
        },
        {
          name: 'Bajo stock',
          data: data.inventario?.bajo_stock_tabla || [],
          columns: [
            { key: 'clasificacion_abc', label: 'ABC' },
            { key: 'Referencia', label: 'Referencia' },
            { key: 'Descripcion', label: 'Descripcion' },
            { key: 'rotacion_proyectada', label: 'Venta diaria esperada' },
            { key: 'Total', label: 'Stock actual' },
            { key: 'cobertura_dias', label: 'Cobertura dias' },
            { key: 'deficit', label: 'Cantidad a comprar' },
          ],
        },
        {
          name: 'Inventario quieto',
          data: data.inventario?.inventario_quieto_tabla || [],
          columns: [
            { key: 'Referencia', label: 'Referencia' },
            { key: 'Descripcion', label: 'Descripcion' },
            { key: 'dias_sin_venta', label: 'Dias sin venta' },
            { key: 'Total', label: 'Stock' },
            { key: 'capital_inmovilizado', label: 'Capital inmovilizado' },
          ],
        },
        {
          name: 'Compras vs ventas',
          data: data.compras?.comparativo || [],
          columns: [
            { key: 'Referencia', label: 'Referencia' },
            { key: 'Descripcion', label: 'Descripcion' },
            { key: 'proveedor', label: 'Proveedor' },
            { key: 'inv_inicial', label: 'Inv inicial' },
            { key: 'uds_compradas', label: 'Comprado' },
            { key: 'uds_vendidas', label: 'Vendido' },
            { key: 'inv_actual', label: 'Inv actual' },
            { key: 'cobertura_dias', label: 'Cobertura dias' },
            { key: 'estado', label: 'Estado' },
          ],
        },
        {
          name: 'Rentabilidad ABC',
          data: data.rentabilidad?.matriz_abc || [],
          columns: [
            { key: 'Referencia', label: 'Referencia' },
            { key: 'nombre', label: 'Producto' },
            { key: 'ingreso_total', label: 'Ingreso' },
            { key: 'utilidad_total', label: 'Utilidad' },
            { key: 'margen_pct', label: 'Margen %' },
            { key: 'matriz_abc', label: 'Matriz ABC' },
          ],
        },
        {
          name: 'Sedes',
          data: data.sedes?.comparativo || [],
          columns: [
            { key: 'sede', label: 'Sede' },
            { key: 'ingresos', label: 'Ingresos' },
            { key: 'unidades', label: 'Unidades' },
            { key: 'facturas', label: 'Facturas' },
            { key: 'ticket', label: 'Ticket' },
          ],
        },
      ], 'Reporte_Farma_Analytics')
    } catch (e) {
      lastError.value = errorMessage(e, 'No se pudo exportar el reporte')
    } finally {
      exporting.value = false
    }
  }

  return {
    status, uploading, exporting, refreshingLive, uploadError, uploadDiagnostic, lastError, files,
    historicalStatus,
    data, loading, errors, settings,
    fmt, fmtN, formatDateTime,
    uploadFiles, checkStatus, resetSession, exportFullReport,
    fetchHistoricalStatus, refreshLiveInformation,
    fetchResumen, fetchVentas, fetchRentabilidad,
    fetchInventario, fetchCompras, fetchSedes, fetchDevoluciones, fetchMetas,
  }
})
