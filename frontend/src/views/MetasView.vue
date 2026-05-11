<template>
  <div>
    <div class="page-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <Target size="32" color="var(--accent)" />
        <h2 style="margin: 0;">Proyección y Metas Sugeridas</h2>
      </div>
      <p style="margin-top: 8px;">Cálculo inteligente de cuotas por sede y vendedor (Run Rate, Momentum y Eficiencia)</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>¿Cómo se calcula esto?</strong></p>
      <ul style="margin-left: 20px; margin-top: 8px;">
        <li><strong>Proyección Base:</strong> Ritmo de venta actual proyectado a 30 días, ajustado por la tendencia (si la sede aceleró o frenó en la segunda quincena).</li>
        <li><strong>Meta Sugerida:</strong> La proyección base multiplicada por un factor de agresividad, garantizando un piso de crecimiento para sedes que vienen en caída.</li>
        <li><strong>Distribución a Vendedores:</strong> No se parte por igual. Se asigna un 70% por su aporte histórico a la sede y un 30% premiando a los que tienen un mejor Ticket Promedio.</li>
      </ul>
    </ModuleInfo>

    <!-- Controls -->
    <div v-if="data" class="filters-bar" style="justify-content: flex-start; gap: 24px;">
      <div class="filter-group">
        <label>Nivel de Exigencia (Agresividad)</label>
        <div style="display: flex; gap: 10px; margin-top: 4px;">
          <button class="btn-agresividad" :class="{ active: agresividad === 'conservador' }" @click="setAgresividad('conservador')">Conservador (+2%)</button>
          <button class="btn-agresividad" :class="{ active: agresividad === 'normal' }" @click="setAgresividad('normal')">Normal (+5%)</button>
          <button class="btn-agresividad" :class="{ active: agresividad === 'agresivo' }" @click="setAgresividad('agresivo')">Agresivo (+10%)</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-3">
      <div v-for="i in 3" :key="i" class="card skeleton" style="height: 100px;"></div>
    </div>
    
    <div v-else-if="data" class="kpi-grid kpi-grid-3">
      <KpiCard :icon="DollarSign" label="Ingreso Actual (Periodo)" :value="store.fmt(data.resumen.ingreso_actual_total)" />
      <KpiCard :icon="TrendingUp" :label="'Proyección Mes (' + data.resumen.dias_mes + 'd)'" :value="store.fmt(data.resumen.proyeccion_total)">
        <template #sub>
          <span style="font-size: 11px; color: var(--fg-muted);">{{ data.resumen.dias_habiles }} hábiles, {{ data.resumen.dias_festivos }} festivos</span>
        </template>
      </KpiCard>
      <div class="cmd-kpi-card" style="border: 1px solid var(--accent-light); background: #f8fafc;">
        <div class="cmd-kpi-icon-wrap" style="background: var(--accent-light);">
          <Target size="18" color="var(--accent)" />
        </div>
        <div class="cmd-kpi-body">
          <span class="cmd-kpi-label" style="color: var(--accent);">Meta Global Sugerida</span>
          <span class="cmd-kpi-value" style="color: var(--accent);">{{ store.fmt(data.resumen.meta_total) }}</span>
          <span class="cmd-kpi-sub">+{{ ((data.resumen.meta_total / data.resumen.proyeccion_total - 1) * 100).toFixed(1) }}% vs Proyección Base</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <div class="empty-icon"><Target size="48" color="var(--border)" /></div>
      <h3>Faltan datos de Ventas</h3>
      <p>Sube el archivo de ventas para calcular las metas.</p>
    </div>

    <div v-if="data" class="metas-container">
      <div v-for="sede in data.sedes" :key="sede.sede" class="card" style="margin-bottom: 20px;">
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
            <tr v-for="v in sede.vendedores" :key="v.nombre">
              <td style="font-weight: 500;">{{ v.nombre }}</td>
              <td>{{ store.fmt(v.ingreso_actual) }}</td>
              <td>{{ store.fmt(v.ticket_promedio) }}</td>
              <td>{{ v.aporte_historico }}%</td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <div style="width: 50px; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
                    <div :style="{ width: v.peso_distribucion + '%', background: 'var(--accent)', height: '100%' }"></div>
                  </div>
                  {{ v.peso_distribucion }}%
                </div>
              </td>
              <td style="text-align: right; font-weight: 700; color: var(--accent);">{{ store.fmt(v.meta) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import { Target, TrendingUp, DollarSign, Store } from 'lucide-vue-next'

const store = useDashboardStore()
const agresividad = ref('normal')
const loading = ref(false)
const data = ref(null)

onMounted(async () => {
  if (store.status.ventas) {
    await fetchMetas()
  }
})

async function setAgresividad(val) {
  agresividad.value = val
  await fetchMetas()
}

async function fetchMetas() {
  loading.value = true
  try {
    const res = await window.axios.get('/api/metas', {
      params: { agresividad: agresividad.value }
    })
    data.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
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
