<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppToastContainer from "../../components/common/AppToastContainer.vue";
import TaskErrorList from "../../components/tasks/TaskErrorList.vue";
import { useTaskPolling } from "../../composables/useTaskPolling";
import { useProjectWorkbenchStore } from "../../stores/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";
import Step1ScriptView from "./Step1ScriptView.vue";
import Step2AssetsView from "./Step2AssetsView.vue";
import Step3StoryboardView from "./Step3StoryboardView.vue";
import Step4MediaView from "./Step4MediaView.vue";
import Step5ExportView from "./Step5ExportView.vue";

const route = useRoute();
const router = useRouter();
const store = useProjectWorkbenchStore();
const toast = useToastStore();
const projectId = computed(() => String(route.params.projectId || ""));
const activeStep = ref(1);
const workbenchUnavailable = ref(false);
const manuallyRefreshing = ref(false);
const autoRefreshing = ref(false);
let polling = useTaskPolling(projectId.value || "");
let autoTimer: number | null = null;

function syncAutoRefreshingFlag() {
  const anyRunning = store.tasks.some((item) => item.status === "RUNNING");
  autoRefreshing.value = anyRunning;
}

async function manualRefresh() {
  if (!projectId.value || manuallyRefreshing.value) return;
  manuallyRefreshing.value = true;
  try {
    await store.refresh(projectId.value);
    syncAutoRefreshingFlag();
    if (store.tasks.some((item) => item.status === "RUNNING")) {
      polling.start();
      if (autoTimer === null) {
        autoTimer = window.setInterval(() => {
          syncAutoRefreshingFlag();
          if (!store.tasks.some((item) => item.status === "RUNNING")) {
            if (autoTimer !== null) {
              clearInterval(autoTimer);
              autoTimer = null;
            }
            autoRefreshing.value = false;
          }
        }, 1500);
      }
    }
    toast.success("数据已刷新");
  } catch (error) {
    toast.error(getErrorMessage(error, "刷新失败"));
  } finally {
    manuallyRefreshing.value = false;
  }
}

onBeforeUnmount(() => {
  if (autoTimer !== null) {
    clearInterval(autoTimer);
    autoTimer = null;
  }
});

async function loadWorkbench(targetProjectId: string) {
  if (!targetProjectId) {
    workbenchUnavailable.value = true;
    router.replace("/projects");
    return;
  }

  try {
    await store.refresh(targetProjectId);
    workbenchUnavailable.value = false;
    polling.stop();
    polling = useTaskPolling(targetProjectId);
    syncAutoRefreshingFlag();
    if (store.tasks.some((item) => item.status === "RUNNING")) {
      polling.start();
      if (autoTimer === null) {
        autoTimer = window.setInterval(() => {
          syncAutoRefreshingFlag();
          if (!store.tasks.some((item) => item.status === "RUNNING")) {
            if (autoTimer !== null) {
              clearInterval(autoTimer);
              autoTimer = null;
            }
            autoRefreshing.value = false;
          }
        }, 1500);
      }
    }
  } catch (error) {
    workbenchUnavailable.value = true;
    polling.stop();
    toast.error(getErrorMessage(error, "项目不存在或已被删除，已返回项目中心"));
    router.replace("/projects");
  }
}

onMounted(async () => {
  await loadWorkbench(projectId.value);
});

watch(
  () => projectId.value,
  async (value, oldValue) => {
    if (value && value === oldValue) return;
    await loadWorkbench(value);
  },
);
</script>

<template>
  <div class="workbench">
    <AppToastContainer />

    <section v-if="workbenchUnavailable" class="card-shell">
      <p class="helper-text">项目不存在或已被删除，正在返回项目中心...</p>
    </section>

    <template v-else>

      <header class="workbench-header">
        <div>
          <h1>AutoVision-AI 工作台</h1>
          <p v-if="store.project">项目：{{ store.project.name }}</p>
          <p v-if="store.project" class="helper-text">
            Step 解锁：{{ store.project.current_step_unlock || 1 }} | 当前任务：{{ store.tasks.length }} 个
            <span v-if="autoRefreshing" class="status-running">（任务运行中，自动刷新已开启）</span>
          </p>
        </div>
        <div class="toolbar workbench-toolbar">
          <button class="ghost-btn" :disabled="!projectId || manuallyRefreshing" @click="manualRefresh">
            {{ manuallyRefreshing ? "刷新中..." : "刷新数据" }}
          </button>
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
    </template>
  </div>
</template>
