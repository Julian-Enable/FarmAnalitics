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

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',              component: HomeView,         name: 'home' },
    { path: '/ventas',        component: VentasView,       name: 'ventas' },
    { path: '/rentabilidad',  component: RentabilidadView, name: 'rentabilidad' },
    { path: '/inventario',    component: InventarioView,   name: 'inventario' },
    { path: '/compras',       component: ComprasView,      name: 'compras' },
    { path: '/sedes',         component: SedesView,        name: 'sedes' },
  ]
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(VueApexCharts)
app.mount('#app')
