<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import AppToastContainer from "../components/common/AppToastContainer.vue";
import { createProject, deleteProject, getProjects } from "../api/projectWorkbench";
import { useToastStore } from "../stores/toast";
import { getErrorMessage } from "../utils/error";

const router = useRouter();
const toast = useToastStore();
const loading = ref(false);
const creating = ref(false);
const deletingId = ref("");
const projects = ref<any[]>([]);

const form = reactive({
  name: "",
  description: "",
  aspect_ratio: "16:9",
  target_width: 1280,
  target_height: 720,
  fps: 24,
});

const hasProjects = computed(() => projects.value.length > 0);

async function loadProjects() {
  loading.value = true;
  try {
    const response = await getProjects();
    projects.value = response.data.data.items || [];
  } catch (error) {
    toast.error(getErrorMessage(error, "加载项目列表失败"));
  } finally {
    loading.value = false;
  }
}

function openWorkbench(projectId: string) {
  router.push(`/projects/${projectId}/workbench`);
}

async function handleCreateProject() {
  if (!form.name.trim()) {
    toast.error("请先输入项目名称");
    return;
  }

  creating.value = true;
  try {
    const response = await createProject({
      name: form.name.trim(),
      description: form.description.trim(),
      aspect_ratio: form.aspect_ratio,
      target_width: Number(form.target_width),
      target_height: Number(form.target_height),
      fps: Number(form.fps),
    });
    const projectId = response.data.data.id;
    toast.success("项目已创建");
    await loadProjects();
    router.push(`/projects/${projectId}/workbench`);
  } catch (error) {
    toast.error(getErrorMessage(error, "创建项目失败"));
  } finally {
    creating.value = false;
  }
}

async function handleDeleteProject(project: any) {
  const confirmed = window.confirm(`确认删除项目“${project.name}”吗？\n\n这会同时删除该项目关联的素材记录和已生成文件。`);
  if (!confirmed) return;

  deletingId.value = project.id;
  try {
    await deleteProject(project.id);
    toast.success(`项目“${project.name}”已删除`);
    await loadProjects();
  } catch (error) {
    toast.error(getErrorMessage(error, "删除项目失败"));
  } finally {
    deletingId.value = "";
  }
}

onMounted(loadProjects);
</script>

<template>
  <div class="project-home">
    <AppToastContainer />

    <header class="workbench-header">
      <div>
        <h1>AutoVision-AI 项目中心</h1>
        <p class="helper-text">支持创建项目、进入工作台和删除历史项目。</p>
      </div>
    </header>

    <section class="card-shell project-create-card">
      <h2>新建项目</h2>
      <div class="form-grid">
        <label class="field">
          <span>项目名称</span>
          <input v-model="form.name" type="text" placeholder="例如：都市夜景短剧" />
        </label>
        <label class="field">
          <span>项目描述</span>
          <input v-model="form.description" type="text" placeholder="可选，用于备注本次项目目标" />
        </label>
        <div class="field-row">
          <label class="field">
            <span>画幅</span>
            <select v-model="form.aspect_ratio">
              <option value="16:9">16:9</option>
              <option value="9:16">9:16</option>
            </select>
          </label>
          <label class="field">
            <span>FPS</span>
            <input v-model.number="form.fps" type="number" min="1" max="60" />
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span>宽度</span>
            <input v-model.number="form.target_width" type="number" min="256" />
          </label>
          <label class="field">
            <span>高度</span>
            <input v-model.number="form.target_height" type="number" min="256" />
          </label>
        </div>
      </div>
      <div class="toolbar">
        <button :disabled="creating" @click="handleCreateProject">
          {{ creating ? "创建中..." : "创建并进入工作台" }}
        </button>
      </div>
    </section>

    <section class="card-shell project-list-card">
      <div class="toolbar toolbar-between">
        <div>
          <h2>已有项目</h2>
          <p class="helper-text">
            {{ loading ? "项目列表加载中..." : hasProjects ? `共 ${projects.length} 个项目` : "当前还没有项目" }}
          </p>
        </div>
        <button :disabled="loading" @click="loadProjects">
          {{ loading ? "刷新中..." : "刷新列表" }}
        </button>
      </div>

      <div v-if="hasProjects" class="list-grid">
        <article v-for="project in projects" :key="project.id" class="item-card">
          <h3>{{ project.name }}</h3>
          <p class="helper-text">状态：{{ project.status }} | Step 解锁：{{ project.current_step_unlock }}</p>
          <p class="helper-text">最近更新时间：{{ project.updated_at || "-" }}</p>
          <div class="toolbar">
            <button @click="openWorkbench(project.id)">进入工作台</button>
            <button
              class="danger-button"
              :disabled="deletingId === project.id"
              @click="handleDeleteProject(project)"
            >
              {{ deletingId === project.id ? "删除中..." : "删除项目" }}
            </button>
          </div>
        </article>
      </div>

      <p v-else class="helper-text">你可以先创建一个项目，再进入五步工作台。</p>
    </section>
  </div>
</template>
