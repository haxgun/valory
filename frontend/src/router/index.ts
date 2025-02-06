import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'VALORY',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/configurator',
      name: 'Configurator',
      component: () => import('@/views/EditorView.vue'),
      meta: { showHeader: true, hideHighlight: true, requiresAuth: true },
    },
    {
      path: '/overlay/:overlayID',
      name: 'Overlay',
      component: () => import('@/views/OverlayView.vue'),
      meta: { hideHighlight: true },
      props: (route) => ({ overlayID: route.params.overlayID }),
    },
    {
      path: '/callback',
      component: () => import('@/views/CallbackView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'Ooops! 404',
      component: () => import('@/views/PageNotFoundView.vue'),
      meta: { hideHighlight: true },
    },
    {
      path: '/unsupported',
      name: 'Unsupported',
      component: () => import('@/views/UnsupportedView.vue'),
      meta: { hideHighlight: true },
    },
  ],
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();

  if (typeof to.name === 'string') {
    document.title = to.name
  }

  const isMobile = window.matchMedia('(max-width: 768px)').matches

  if (isMobile && to.name !== 'Unsupported') {
    next({ name: 'Unsupported' })
  } else if (!isMobile && to.name === 'Unsupported') {
    next({ name: 'VALORY' })
  } else {
    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
      next("/");
    } else {
      next();
    }
  }
})

export default router
