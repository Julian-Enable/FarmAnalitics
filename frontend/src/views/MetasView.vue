<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <Target size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Proyección y Metas Sugeridas</h2>
      </div>
      <p style="margin-top: 8px;">Cálculo por mes anterior, comparativo histórico anual e incremento objetivo por sede.</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Cómo se calcula ahora Proyección y Metas?</strong></p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>1. Base mensual real:</strong> Se toma la venta bruta del mes anterior por sede y se calcula su promedio diario con los días calendario del mes (operación domingo a domingo, festivos incluidos).</li>
        <li><strong>2. Proyección del periodo objetivo:</strong> Ese promedio diario se proyecta al mes o rango seleccionado para obtener la <strong>Proyección Base</strong>.</li>
        <li><strong>3. Contexto histórico anual:</strong> Se compara el mismo par de meses del año anterior (mes objetivo y su mes previo) para estimar el incremento histórico de referencia.</li>
        <li><strong>4. Meta sugerida:</strong> La meta se calcula aplicando a la proyección base el incremento histórico y el nivel de exigencia (Conservador, Normal o Agresivo).</li>
        <li><strong>5. Distribución por vendedores:</strong> La meta de sede se reparte en partes iguales entre vendedores fijos (se excluyen aportes menores al 5%).</li>
        <li><strong>6. Fallback automático de periodo:</strong> Si el mes actual no tiene base en datos, el sistema proyecta con el último mes disponible y avanza al mes siguiente para evitar metas en cero.</li>
      </ul>
    </ModuleInfo>

    <!-- Controls -->
    <div v-if="data || store.status.ventas" class="filters-bar" style="justify-content: flex-start; gap: 24px; flex-wrap: wrap;">
      <div class="filter-group">
        <label>Nivel de Exigencia (Agresividad)</label>
        <div style="display: flex; gap: 10px; margin-top: 4px;">
          <button class="btn-agresividad" :class="{ active: agresividad === 'conservador' }" @click="setAgresividad('conservador')">Conservador (+2%)</button>
          <button class="btn-agresividad" :class="{ active: agresividad === 'normal' }" @click="setAgresividad('normal')">Normal (+5%)</button>
          <button class="btn-agresividad" :class="{ active: agresividad === 'agresivo' }" @click="setAgresividad('agresivo')">Agresivo (+10%)</button>
        </div>
      </div>
      
      <div class="filter-group">
        <label>Proyectar Desde</label>
        <input type="date" v-model="fechaIni" @change="applyFilters" style="margin-top: 4px;" />
      </div>
      <div class="filter-group">
        <label>Proyectar Hasta</label>
        <input type="date" v-model="fechaFin" @change="applyFilters" style="margin-top: 4px;" />
      </div>
    </div>

    <div v-if="weightError" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ weightError }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-3">
      <div v-for="i in 3" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    
    <div v-else-if="data" class="kpi-grid kpi-grid-3">
      <KpiCard :icon="DollarSign" label="Ingreso Base (Histórico)" :value="store.fmt(data.resumen.ingreso_actual_total)" />
      <KpiCard :icon="TrendingUp" :label="'Proyección Mes (' + data.resumen.dias_mes + 'd)'" :value="store.fmt(data.resumen.proyeccion_total)">
        <template #sub>
          <div style="font-size: 11px; color: var(--fg-muted); display: flex; flex-direction: column; gap: 2px; margin-top: 2px;">
            <span>{{ data.resumen.dias_habiles }} hábiles, {{ data.resumen.dias_festivos }} festivos</span>
            <span><strong>Base histórica:</strong> {{ data.resumen.mes_base_usado }}</span>
          </div>
        </template>
      </KpiCard>
      <div class="cmd-kpi-card" style="border: 1px solid var(--accent-light); background: #f8fafc;">
        <div class="cmd-kpi-icon-wrap" style="background: var(--accent-light);">
          <Target size="18" color="var(--accent)" />
        </div>
        <div class="cmd-kpi-body">
          <span class="cmd-kpi-label" style="color: var(--accent);">Meta Global Sugerida</span>
          <span class="cmd-kpi-value" style="color: var(--accent);">{{ store.fmt(data.resumen.meta_total) }}</span>
          <span class="cmd-kpi-sub">{{ metaVsProjectionLabel }}</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <div class="empty-icon"><Target size="48" color="var(--border)" /></div>
      <h3>Faltan datos de Ventas</h3>
      <p>Sube el archivo de ventas para calcular las metas.</p>
    </div>

    <div v-if="data" class="metas-container">
      <div v-for="sede in processedSedes" :key="sede.sede" class="card" style="margin-bottom: 20px;">
        <div class="sede-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 16px;">
          <div>
            <h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">
              <Store size="20" color="var(--accent)" /> {{ sede.sede }}
            </h3>
            <div style="font-size: 12px; color: var(--fg-muted); margin-top: 4px; display: flex; gap: 16px;">
              <span><strong>IDP (Promedio Diario):</strong> {{ store.fmt(sede.idp) }}</span>
              <span><strong>Momentum:</strong> <span :style="{color: sede.tendencia >= 1 ? 'var(--green)' : 'var(--red)'}">{{ sede.tendencia >= 1 ? '▲' : '▼' }} {{ sede.tendencia }}x</span></span>
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 12px; color: var(--fg-muted);">Meta Sugerida Sede</div>
            <div style="font-size: 24px; font-weight: 700; color: var(--accent);">{{ store.fmt(sede.meta_sugerida) }}</div>
          </div>
        </div>
        
        <table class="data-table">
          <thead>
            <tr>
              <th>Vendedor</th>
              <th>Ingreso Actual</th>
              <th>Ticket Promedio</th>
              <th>Aporte Hist. (%)</th>
              <th>Peso Asignado (%)</th>
              <th style="text-align: right; color: var(--accent);">Meta Asignada</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in sede.vendedores_calc" :key="v.nombre">
              <td style="font-weight: 500;">{{ v.nombre }}</td>
              <td>{{ store.fmt(v.ingreso_actual) }}</td>
              <td>{{ store.fmt(v.ticket_promedio) }}</td>
              <td>{{ v.aporte_historico }}%</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <input 
                    type="number" 
                    min="0" 
                    max="100" 
                    :value="v.peso_final.toFixed(1)"
                    @blur="updateWeight(sede.sede, v.nombre, $event.target.value)"
                    @keyup.enter="updateWeight(sede.sede, v.nombre, $event.target.value)"
                    style="width: 50px; padding: 2px 4px; border: 1px solid var(--border); border-radius: 4px; text-align: center; font-size: 12px;"
                  /> <span style="font-size: 12px; color: var(--fg-muted);">%</span>
                  <button v-if="v.isLocked" @click="clearWeight(sede.sede, v.nombre)" title="Restablecer (Equitativo)" style="background: none; border: none; cursor: pointer; color: var(--red); padding: 0; display: flex;">
                    <RotateCcw size="14" />
                  </button>
                </div>
                <div style="width: 60px; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; margin-top: 4px;">
                  <div :style="{ width: v.peso_final + '%', background: v.isLocked ? '#8b5cf6' : 'var(--accent)', height: '100%' }"></div>
                </div>
              </td>
              <td style="text-align: right; font-weight: 700; color: var(--accent);">{{ store.fmt(v.meta_final) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import { Target, TrendingUp, DollarSign, Store, RotateCcw } from 'lucide-vue-next'

const store = useDashboardStore()
const agresividad = ref('normal')
const fechaIni = ref('')
const fechaFin = ref('')
const userOverrides = ref({}) // { 'Sede': { 'Vendedor': 30 } }
const weightError = ref('')

const loading = computed(() => store.loading.metas)
const data = computed(() => store.data.metas)

const metaVsProjectionLabel = computed(() => {
  const resumen = data.value?.resumen
  if (!resumen?.proyeccion_total) return 'Sin proyección base'
  const pct = ((resumen.meta_total / resumen.proyeccion_total - 1) * 100)
  if (!Number.isFinite(pct)) return 'Sin proyección base'
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% vs Proyección Base`
})

// Computed property que inyecta las asignaciones personalizadas de peso
const processedSedes = computed(() => {
  if (!data.value || !data.value.sedes) return []
  
  return data.value.sedes.map(sede => {
    const overrides = userOverrides.value[sede.sede] || {}
    let totalLockedWeight = 0
    let lockedCount = 0
    
    // Identificar pesos bloqueados
    sede.vendedores.forEach(v => {
      if (overrides[v.nombre] !== undefined) {
        totalLockedWeight += overrides[v.nombre]
        lockedCount++
      }
    })
    
    const remainingWeight = Math.max(0, 100 - totalLockedWeight)
    const unlockedCount = Math.max(1, sede.vendedores.length - lockedCount)
    const equalUnlockedWeight = remainingWeight / unlockedCount
    
    // Asignar pesos finales
    const newVends = sede.vendedores.map(v => {
      const isLocked = overrides[v.nombre] !== undefined
      const finalWeight = isLocked ? overrides[v.nombre] : equalUnlockedWeight
      const finalMeta = (sede.meta_sugerida * finalWeight) / 100
      
      return {
        ...v,
        isLocked,
        peso_final: finalWeight,
        meta_final: finalMeta
      }
    })
    
    return {
      ...sede,
      vendedores_calc: newVends
    }
  })
})

onMounted(async () => {
  if (!data.value) {
    await store.fetchMetas(agresividad.value, fechaIni.value || null, fechaFin.value || null)
  }
})

async function setAgresividad(val) {
  agresividad.value = val
  await applyFilters()
}

async function applyFilters() {
  await store.fetchMetas(agresividad.value, fechaIni.value || null, fechaFin.value || null)
}

function updateWeight(sedeName, vendName, val) {
  const num = parseFloat(val)
  if (isNaN(num) || num < 0 || num > 100) return

  const sedeOverrides = { ...(userOverrides.value[sedeName] || {}) }
  const othersTotal = Object.entries(sedeOverrides)
    .filter(([name]) => name !== vendName)
    .reduce((acc, [, weight]) => acc + Number(weight || 0), 0)

  if (othersTotal + num > 100) {
    weightError.value = `La suma de pesos bloqueados en ${sedeName} no puede superar 100%.`
    return
  }

  weightError.value = ''
  sedeOverrides[vendName] = num
  userOverrides.value[sedeName] = sedeOverrides
}

function clearWeight(sedeName, vendName) {
  if (userOverrides.value[sedeName]) {
    delete userOverrides.value[sedeName][vendName]
    weightError.value = ''
  }
}
</script>

<style scoped>
.btn-agresividad {
  background: white;
  border: 1px solid var(--border);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--fg);
  transition: all 0.2s;
}
.btn-agresividad:hover {
  background: #f8fafc;
}
.btn-agresividad.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
</style>

