import { createRouter, createWebHistory } from "vue-router";

import ProjectWorkbench from "../views/workbench/ProjectWorkbench.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/projects/demo/workbench",
    },
    {
      path: "/projects/:projectId/workbench",
      name: "workbench",
      component: ProjectWorkbench,
    },
  ],
});

export default router;
