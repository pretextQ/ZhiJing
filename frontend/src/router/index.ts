import { createRouter, createWebHistory } from 'vue-router'
import CoursesView from '../views/CoursesView.vue'
import RoomView from '../views/RoomView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'room', component: RoomView },
    { path: '/courses', name: 'courses', component: CoursesView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior() {
    return { top: 0, left: 0 }
  },
})

export default router
