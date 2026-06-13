import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import VueApexCharts from 'vue3-apexcharts'

import App from './App.vue'
import './assets/main.css'

// Vistas
import HomeView          from './views/HomeView.vue'
import VentasView        from './views/VentasView.vue'
import RentabilidadView  from './views/RentabilidadView.vue'
import InventarioView    from './views/InventarioView.vue'
import ComprasView       from './views/ComprasView.vue'
import SedesView         from './views/SedesView.vue'
import DevolucionesView  from './views/DevolucionesView.vue'
import MetasView         from './views/MetasView.vue'
import GerenciaView      from './views/GerenciaView.vue'
import DomiciliosView    from './views/DomiciliosView.vue'
import ComisionesView    from './views/ComisionesView.vue'
import MermasView        from './views/MermasView.vue'
import DescuentosView    from './views/DescuentosView.vue'
import CronicosView      from './views/CronicosView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',              component: HomeView,         name: 'home' },
    { path: '/ventas',        component: VentasView,       name: 'ventas' },
    { path: '/rentabilidad',  component: RentabilidadView, name: 'rentabilidad' },
    { path: '/inventario',    component: InventarioView,   name: 'inventario' },
    { path: '/compras',       component: ComprasView,      name: 'compras' },
    { path: '/sedes',         component: SedesView,        name: 'sedes' },
    { path: '/devoluciones',  component: DevolucionesView, name: 'devoluciones' },
    { path: '/domicilios',    component: DomiciliosView,   name: 'domicilios' },
    { path: '/comisiones',    component: ComisionesView,   name: 'comisiones' },
    { path: '/mermas',        component: MermasView,       name: 'mermas' },
    { path: '/descuentos',    component: DescuentosView,   name: 'descuentos' },
    { path: '/cronicos',      component: CronicosView,     name: 'cronicos' },
    { path: '/metas',         component: MetasView,        name: 'metas' },
    { path: '/gerencia',      component: GerenciaView,     name: 'gerencia' },
  ]
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(VueApexCharts)
app.mount('#app')
