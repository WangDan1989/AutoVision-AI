import { createRouter, createWebHistory } from "vue-router";

import ProjectHomeView from "../views/ProjectHomeView.vue";
import ProjectWorkbench from "../views/workbench/ProjectWorkbench.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/projects",
    },
    {
      path: "/projects",
      name: "projects",
      component: ProjectHomeView,
    },
    {
      path: "/projects/:projectId/workbench",
      name: "workbench",
      component: ProjectWorkbench,
    },
  ],
});

export default router;
