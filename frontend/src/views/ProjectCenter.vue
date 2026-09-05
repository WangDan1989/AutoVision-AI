<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { createProject, getProjects } from "../api/projectWorkbench";
import { useToastStore } from "../stores/toast";
import { getErrorMessage } from "../utils/error";

const router = useRouter();
const toast = useToastStore();

const loading = ref(false);
const items = ref<any[]>([]);
const creating = ref(false);
const showCreateForm = ref(false);
const form = ref({ name: "", description: "" });

const canSubmit = computed(() => !!form.value.name.trim());

async function refresh() {
  loading.value = true;
  try {
    const res = await getProjects();
    const data = res?.data?.data ?? res?.data ?? {};
    items.value = Array.isArray(data) ? data : data?.items ?? [];
  } catch (error) {
    toast.error(getErrorMessage(error, "加载项目列表失败"));
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  if (!canSubmit.value) {
    toast.error("请先填写项目名称");
    return;
  }
  creating.value = true;
  try {
    const res = await createProject({
      name: form.value.name.trim(),
      description: form.value.description?.trim() || undefined,
    });
    const project = res?.data?.data ?? res?.data;
    const projectId = project?.id;
    toast.success(`项目「${form.value.name}」已创建`);
    showCreateForm.value = false;
    form.value = { name: "", description: "" };
    await refresh();
    if (projectId) {
      router.push(`/projects/${projectId}/workbench`);
    }
  } catch (error) {
    toast.error(getErrorMessage(error, "创建项目失败"));
  } finally {
    creating.value = false;
  }
}

function enterWorkbench(projectId: string) {
  router.push(`/projects/${projectId}/workbench`);
}

function formatDate(value: string | undefined) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

onMounted(refresh);
</script>

<template>
  <div class="project-center">
    <header class="pc-header">
      <div>
        <h1>AutoVision-AI 项目中心</h1>
        <p class="pc-subtitle">在这里管理你的短片 / 绘本视频项目</p>
      </div>
      <button class="pc-primary" :disabled="creating" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? "取消新建" : "+ 新建项目" }}
      </button>
    </header>

    <section v-if="showCreateForm" class="card-shell pc-create-card">
      <h2>新建项目</h2>
      <div class="field">
        <label>项目名称</label>
        <input v-model="form.name" placeholder="例如：校园悬疑短片 01" maxlength="64" />
      </div>
      <div class="field">
        <label>项目简介（可选）</label>
        <textarea
          v-model="form.description"
          rows="3"
          class="text-area"
          placeholder="简单描述这个项目的主题或用途"
        />
      </div>
      <div class="toolbar">
        <button :disabled="!canSubmit || creating" @click="handleCreate">
          {{ creating ? "创建中..." : "创建并进入工作台" }}
        </button>
      </div>
    </section>

    <section class="pc-list-header">
      <h2>全部项目</h2>
      <span v-if="!loading" class="helper-text">共 {{ items.length }} 个</span>
    </section>

    <div v-if="loading" class="helper-text">加载中...</div>

    <div v-else-if="!items.length" class="card-shell pc-empty">
      <p>还没有项目，点击右上角「新建项目」开始吧。</p>
    </div>

    <div v-else class="list-grid">
      <article v-for="project in items" :key="project.id" class="item-card pc-project-card">
        <h3>{{ project.name || "未命名项目" }}</h3>
        <p v-if="project.description" class="pc-desc">{{ project.description }}</p>
        <div class="pc-meta helper-text">
          <span>创建时间：{{ formatDate(project.created_at) }}</span>
        </div>
        <div class="toolbar pc-actions">
          <button class="pc-primary" @click="enterWorkbench(project.id)">进入工作台</button>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.project-center {
  padding: 32px 40px;
  max-width: 1280px;
  margin: 0 auto;
}

.pc-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}

.pc-header h1 {
  margin: 0 0 4px;
  font-size: 28px;
}

.pc-subtitle {
  margin: 0;
  color: #5a5f73;
}

.pc-primary {
  background: #4c3cff;
  color: #fff;
  border-color: #4c3cff;
  font-weight: 600;
}

.pc-create-card {
  margin-bottom: 24px;
}

.pc-create-card h2 {
  margin: 0 0 12px;
  font-size: 18px;
}

.pc-list-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.pc-list-header h2 {
  margin: 0;
  font-size: 20px;
}

.pc-empty {
  text-align: center;
  padding: 40px 16px;
  color: #5a5f73;
}

.pc-project-card h3 {
  margin: 0 0 8px;
  font-size: 18px;
}

.pc-desc {
  margin: 0 0 12px;
  color: #3f3a5c;
  min-height: 48px;
}

.pc-meta {
  margin-bottom: 12px;
}

.pc-actions {
  margin-bottom: 0;
}
</style>
