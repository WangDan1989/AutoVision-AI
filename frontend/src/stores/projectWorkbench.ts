import { defineStore } from "pinia";
import { ref } from "vue";

import { getProject, getTasks } from "../api/projectWorkbench";

export const useProjectWorkbenchStore = defineStore("projectWorkbench", () => {
  const project = ref<any>(null);
  const tasks = ref<any[]>([]);
  const loading = ref(false);

  async function refresh(projectId: string) {
    loading.value = true;
    try {
      const [projectRes, tasksRes] = await Promise.all([
        getProject(projectId),
        getTasks(projectId),
      ]);
      project.value = projectRes.data.data;
      tasks.value = tasksRes.data.data.items;
    } finally {
      loading.value = false;
    }
  }

  return {
    project,
    tasks,
    loading,
    refresh,
  };
});
