import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/', component: () => import('./pages/Overview.vue') },
  { path: '/metrics', component: () => import('./pages/MetricList.vue') },
  { path: '/metrics/:code', component: () => import('./pages/MetricDetail.vue'), props: true },
  { path: '/metrics/:code/edit', component: () => import('./pages/MetricEditor.vue'), props: true },
  { path: '/metrics/new', component: () => import('./pages/MetricEditor.vue') },
  { path: '/requests', component: () => import('./pages/ChangeRequests.vue') },
  { path: '/requests/:id', component: () => import('./pages/ChangeRequestDetail.vue'), props: true },
  { path: '/scheduled-reports', component: () => import('./pages/ScheduledReports.vue') },
  { path: '/quality', component: () => import('./pages/QualityBoard.vue') },
  { path: '/lineage', component: () => import('./pages/Lineage.vue') },
  { path: '/subscriptions', component: () => import('./pages/Subscriptions.vue') },
  { path: '/settings', component: () => import('./pages/Settings.vue') },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
