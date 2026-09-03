<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppToastContainer from "../../components/common/AppToastContainer.vue";
import TaskErrorList from "../../components/tasks/TaskErrorList.vue";
import { useTaskPolling } from "../../composables/useTaskPolling";
import { useProjectWorkbenchStore } from "../../stores/projectWorkbench";
import Step1ScriptView from "./Step1ScriptView.vue";
import Step2AssetsView from "./Step2AssetsView.vue";
import Step3StoryboardView from "./Step3StoryboardView.vue";
import Step4MediaView from "./Step4MediaView.vue";
import Step5ExportView from "./Step5ExportView.vue";

const route = useRoute();
const router = useRouter();
const store = useProjectWorkbenchStore();
const projectId = computed(() => String(route.params.projectId || "demo"));
const activeStep = ref(1);
const polling = useTaskPolling(projectId.value);

onMounted(async () => {
  await store.refresh(projectId.value);
  if (store.tasks.some((item) => item.status === "RUNNING")) {
    polling.start();
  }
});
</script>

<template>
  <div class="workbench">
    <AppToastContainer />

    <header class="workbench-header">
      <div>
        <h1>AutoVision-AI 工作台</h1>
        <p v-if="store.project">项目：{{ store.project.name }}</p>
      </div>
      <div class="toolbar">
        <button @click="router.push('/projects')">返回项目中心</button>
      </div>
    </header>

    <TaskErrorList :tasks="store.tasks" />

    <nav class="step-tabs">
      <button v-for="step in 5" :key="step" :class="{ active: activeStep === step }" @click="activeStep = step">
        Step {{ step }}
      </button>
    </nav>

    <Step1ScriptView v-if="activeStep === 1" :project-id="projectId" :segments="store.segments" @refresh="store.refresh(projectId)" />
    <Step2AssetsView v-if="activeStep === 2" :project-id="projectId" :assets="store.assets" @refresh="store.refresh(projectId)" />
    <Step3StoryboardView
      v-if="activeStep === 3"
      :project-id="projectId"
      :project="store.project"
      :segments="store.segments"
      :frames="store.frames"
      @refresh="store.refresh(projectId)"
    />
    <Step4MediaView
      v-if="activeStep === 4"
      :project-id="projectId"
      :project="store.project"
      :segments="store.segments"
      :frames="store.frames"
      :videos="store.videos"
      :audio-tracks="store.audioTracks"
      :tasks="store.tasks"
      @refresh="store.refresh(projectId)"
    />
    <Step5ExportView
      v-if="activeStep === 5"
      :project-id="projectId"
      :project="store.project"
      :segments="store.segments"
      :frames="store.frames"
      :videos="store.videos"
      :audio-tracks="store.audioTracks"
      :exports-list="store.exportsList"
      @refresh="store.refresh(projectId)"
    />
  </div>
</template>
