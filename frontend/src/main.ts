import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/tokens.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/themes.css'
import './styles/courses.css'

createApp(App).use(createPinia()).use(router).mount('#app')
