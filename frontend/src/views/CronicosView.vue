<template>
  <div>
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <PhoneCall size="32" color="var(--accent)" />
        <h2 style="margin:0;">Pacientes Crónicos — Listados de llamadas</h2>
      </div>
      <p style="margin-top:8px;">Clientes que compran un medicamento de forma recurrente, para llamarlos y no perder la recompra.</p>
      <div class="accent-bar"></div>
    </div>

    <ModuleInfo>
      <p><strong>Los dos listados son clientes que compran el mismo medicamento de forma recurrente y sostenida</strong> (compraron en al menos <strong>3 meses distintos</strong>, con frecuencia regular de 15–75 días — no 3 compras juntas en pocos días). La diferencia es el momento, no el tipo de cliente. Para cada uno se estima cuándo se le acaba según <em>su</em> ritmo de compra:</p>
      <ul style="margin-left:20px;margin-top:8px;">
        <li><strong>Recurrentes por agotarse:</strong> aún tienen medicamento pero se les acaba en los próximos días → llamarlos <em>antes</em> para asegurar la recompra.</li>
        <li><strong>Abandonaron:</strong> ya pasaron su fecha esperada y no han vuelto (hasta 180 días vencidos = abandono del año actual) → llamarlos para recuperarlos.</li>
      </ul>
    </ModuleInfo>

    <div v-if="store.errors.cronicos" class="card" style="border-color:#fecdd3;color:#be123c;margin-bottom:16px;background:#fff1f2;">
      {{ store.errors.cronicos }}
    </div>

    <div v-if="loading" class="kpi-grid kpi-grid-4">
      <div v-for="i in 3" :key="i" class="card skeleton" style="height:100px;"></div>
    </div>

    <template v-else-if="data">
      <div class="kpi-grid kpi-grid-4" style="margin-bottom:16px;">
        <KpiCard :icon="Users" label="Pacientes Crónicos (recurrentes)" :value="store.fmtN(data.kpis.clientes_cronicos)" />
        <KpiCard :icon="CalendarClock" label="Recurrentes por agotarse" :value="store.fmtN(data.kpis.n_proximos)" />
        <KpiCard :icon="PhoneCall" label="Abandonaron (recuperar)" :value="store.fmtN(data.kpis.n_recuperar)" />
        <KpiCard :icon="Calendar" label="Fecha de corte" :value="data.kpis.fecha_corte" />
      </div>

      <div class="tabs" style="margin-bottom:12px;">
        <button :class="{ active: tab === 'proximos' }" @click="tab = 'proximos'">
          ⏰ Recurrentes por agotarse ({{ data.proximos.length }})
        </button>
        <button :class="{ active: tab === 'recuperar' }" @click="tab = 'recuperar'">
          📞 Abandonaron — recuperar ({{ data.recuperar.length }})
        </button>
      </div>

      <div class="card">
        <div class="section-header-row">
          <SectionTitle :icon="tab === 'recuperar' ? PhoneCall : CalendarClock"
                        :title="tab === 'recuperar' ? 'Recurrentes que abandonaron (no volvieron por su medicamento)' : 'Recurrentes activos por quedarse sin medicamento'" />
          <button class="export-btn" @click="exportLista"><Download size="16" /> Exportar lista de llamadas</button>
        </div>
        <input v-model="buscar" placeholder="🔍 Buscar por nombre o medicamento..." style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:12px;" />
        <div style="overflow-x:auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Cliente</th><th>Teléfono</th><th>Medicamento</th><th>Compra cada</th>
                <th>Última compra</th>
                <th>{{ tab === 'recuperar' ? 'Vencido hace' : 'Se le acaba en' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in paginado" :key="i">
                <td style="font-weight:600;">{{ r.Nombre }}</td>
                <td style="font-variant-numeric:tabular-nums;">{{ r.telefono || '—' }}</td>
                <td>{{ r.medicamento }}</td>
                <td>{{ Math.round(r.intervalo) }} días</td>
                <td>{{ formatDate(r.ultima) }}</td>
                <td>
                  <span v-if="tab === 'recuperar'" class="badge badge-red">{{ r.dias_vs_esperada }} días</span>
                  <span v-else class="badge" :class="r.dias_para_acabar <= 1 ? 'badge-red' : 'badge-amber'">{{ r.dias_para_acabar }} días</span>
                </td>
              </tr>
              <tr v-if="!paginado.length"><td colspan="6" style="text-align:center;color:var(--fg-muted);">Sin resultados.</td></tr>
            </tbody>
          </table>
        </div>
        <Paginator v-model="page" :totalItems="filtrada.length" :itemsPerPage="20" />
      </div>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><PhoneCall size="48" color="var(--border)" /></div>
      <h3>Faltan datos</h3>
      <p>Se requieren ventas con cliente identificado. Actualiza la información desde tu PC.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import KpiCard from '../components/ui/KpiCard.vue'
import SectionTitle from '../components/ui/SectionTitle.vue'
import ModuleInfo from '../components/ui/ModuleInfo.vue'
import Paginator from '../components/ui/Paginator.vue'
import { exportToCSV } from '../utils/export'
import { PhoneCall, CalendarClock, Users, Calendar, Download } from 'lucide-vue-next'

const store = useDashboardStore()
const data = computed(() => store.data.cronicos)
const loading = computed(() => store.loading.cronicos)
const tab = ref('proximos')
const buscar = ref('')
const page = ref(1)

const lista = computed(() => (tab.value === 'recuperar' ? data.value?.recuperar : data.value?.proximos) || [])
const filtrada = computed(() => {
  const q = buscar.value.trim().toLowerCase()
  if (!q) return lista.value
  return lista.value.filter(r => (r.Nombre || '').toLowerCase().includes(q) || (r.medicamento || '').toLowerCase().includes(q))
})
const paginado = computed(() => filtrada.value.slice((page.value - 1) * 20, page.value * 20))

watch([tab, buscar], () => { page.value = 1 })

function formatDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('es-CO')
}

function exportLista() {
  const base = [
    { key: 'Nombre', label: 'Cliente' },
    { key: 'telefono', label: 'Telefono' },
    { key: 'medicamento', label: 'Medicamento' },
    { key: 'intervalo', label: 'Compra cada (dias)', formatter: v => Math.round(v) },
    { key: 'ultima', label: 'Ultima compra', formatter: formatDate },
  ]
  const cols = tab.value === 'recuperar'
    ? [...base, { key: 'dias_vs_esperada', label: 'Vencido hace (dias)' }]
    : [...base, { key: 'dias_para_acabar', label: 'Se le acaba en (dias)' }]
  exportToCSV(filtrada.value, cols, tab.value === 'recuperar' ? 'Llamadas_Recuperar_Cronicos' : 'Llamadas_Proactivo_Cronicos')
}

onMounted(() => { if (store.status.cronicos && !data.value) store.fetchCronicos() })
</script>

<style scoped>
.tabs { display: flex; gap: 8px; }
.tabs button {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 16px; cursor: pointer; color: var(--fg-muted); font-weight: 600; font-size: 13px;
}
.tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
</style>
