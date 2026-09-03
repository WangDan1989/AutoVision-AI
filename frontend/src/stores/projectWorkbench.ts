import { defineStore } from "pinia";
import { ref } from "vue";

import { getAssets, getFrames, getProject, getSegments, getTasks } from "../api/projectWorkbench";

export const useProjectWorkbenchStore = defineStore("projectWorkbench", () => {
  const project = ref<any>(null);
  const tasks = ref<any[]>([]);
  const segments = ref<any[]>([]);
  const assets = ref<any[]>([]);
  const frames = ref<any[]>([]);
  const loading = ref(false);

  async function refresh(projectId: string) {
    loading.value = true;
    try {
      const [projectRes, tasksRes, segmentsRes, assetsRes, framesRes] = await Promise.all([
        getProject(projectId),
        getTasks(projectId),
        getSegments(projectId),
        getAssets(projectId),
        getFrames(projectId),
      ]);
      project.value = projectRes.data.data;
      tasks.value = tasksRes.data.data.items;
      segments.value = segmentsRes.data.data.items;
      assets.value = assetsRes.data.data.items;
      frames.value = framesRes.data.data.items;
    } finally {
      loading.value = false;
    }
  }

  return {
    project,
    tasks,
    segments,
    assets,
    frames,
    loading,
    refresh,
  };
});
