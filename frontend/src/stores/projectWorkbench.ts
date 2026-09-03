import { defineStore } from "pinia";
import { ref } from "vue";

import { getAssets, getAudioTracks, getExports, getFrames, getProject, getSegments, getTasks, getVideos } from "../api/projectWorkbench";

export const useProjectWorkbenchStore = defineStore("projectWorkbench", () => {
  const project = ref<any>(null);
  const tasks = ref<any[]>([]);
  const segments = ref<any[]>([]);
  const assets = ref<any[]>([]);
  const frames = ref<any[]>([]);
  const videos = ref<any[]>([]);
  const audioTracks = ref<any[]>([]);
  const exportsList = ref<any[]>([]);
  const loading = ref(false);

  async function refresh(projectId: string) {
    loading.value = true;
    try {
      const [projectRes, tasksRes, segmentsRes, assetsRes, framesRes, videosRes, audioRes, exportsRes] = await Promise.all([
        getProject(projectId),
        getTasks(projectId),
        getSegments(projectId),
        getAssets(projectId),
        getFrames(projectId),
        getVideos(projectId),
        getAudioTracks(projectId),
        getExports(projectId),
      ]);
      project.value = projectRes.data.data;
      tasks.value = tasksRes.data.data.items;
      segments.value = segmentsRes.data.data.items;
      assets.value = assetsRes.data.data.items;
      frames.value = framesRes.data.data.items;
      videos.value = videosRes.data.data.items;
      audioTracks.value = audioRes.data.data.items;
      exportsList.value = exportsRes.data.data.items;
    } finally {
      loading.value = false;
    }
  }

  function applyProjectPreferences(preferences: any, updatedAt?: string) {
    if (!project.value) return;
    project.value = {
      ...project.value,
      preferences,
      updated_at: updatedAt || project.value.updated_at,
    };
  }

  return {
    project,
    tasks,
    segments,
    assets,
    frames,
    videos,
    audioTracks,
    exportsList,
    loading,
    refresh,
    applyProjectPreferences,
  };
});
