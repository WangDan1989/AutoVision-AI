<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { createProject, deleteProject, getProjects } from "../api/projectWorkbench";
import { useToastStore } from "../stores/toast";
import { getErrorMessage } from "../utils/error";

const router = useRouter();
const toast = useToastStore();

const loading = ref(false);
const items = ref<any[]>([]);
const creating = ref(false);
const showCreateForm = ref(false);
const form = ref({
  name: "",
  description: "",
  aspect_ratio: "16:9" as "16:9" | "9:16",
  fps: 24,
  target_width: 1280,
  target_height: 720,
});
const deletingIds = ref<Set<string>>(new Set());

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
      aspect_ratio: form.value.aspect_ratio || "16:9",
      fps: Number(form.value.fps) || 24,
      target_width: Number(form.value.target_width) || 1280,
      target_height: Number(form.value.target_height) || 720,
    });
    const project = res?.data?.data ?? res?.data;
    const projectId = project?.id;
    toast.success(
      `项目「${form.value.name}」已创建（${form.value.aspect_ratio || "16:9"} / ${Number(form.value.fps) || 24}fps / ${Number(form.value.target_width) || 1280}×${Number(form.value.target_height) || 720}）`
    );
    showCreateForm.value = false;
    form.value = {
      name: "",
      description: "",
      aspect_ratio: "16:9",
      fps: 24,
      target_width: 1280,
      target_height: 720,
    };
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

async function handleDelete(project: any) {
  const ok = window.confirm(`确认删除项目「${project.name || "未命名项目"}」吗？此操作无法撤销。`);
  if (!ok) return;
  deletingIds.value.add(project.id);
  try {
    const res = await deleteProject(project.id);
    const payload = res?.data?.data ?? res?.data;
    toast.success(
      `已删除项目「${project.name || "未命名项目"}」（删除 ${payload?.deleted_rows ? Object.values(payload.deleted_rows).reduce((a: number, b: number) => a + b, 0) : 0} 条记录，${payload?.deleted_files ?? 0} 个文件）`
    );
    await refresh();
  } catch (error) {
    toast.error(getErrorMessage(error, "删除项目失败"));
  } finally {
    deletingIds.value.delete(project.id);
  }
}

function formatDate(value: string | undefined) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatStep(unlock: number | undefined) {
  const stepNames = ["", "1. 剧本拆解", "2. 资产池", "3. 分镜首帧", "4. 音频与视频", "5. 导出成片"];
  return stepNames[unlock ?? 1] || stepNames[1];
}

onMounted(refresh);
</script>

<template>
  <div class="project-center">
    <header class="pc-header">
      <div>
        <h1>AutoVision-AI 项目中心</h1>
        <p class="pc-subtitle">支持创建项目、进入工作台和删除历史项目。</p>
      </div>
      <button class="pc-primary" :disabled="creating" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? "取消新建" : "+ 新建项目" }}
      </button>
    </header>

    <section v-if="showCreateForm" class="card-shell pc-create-card">
      <h2>新建项目</h2>
      <div class="field">
        <label>项目名称</label>
        <input v-model="form.name" placeholder="例如：都市夜景短剧" maxlength="64" />
      </div>
      <div class="field">
        <label>项目描述</label>
        <textarea
          v-model="form.description"
          rows="2"
          class="text-area"
          placeholder="可选，用于备注本次项目目标"
        />
      </div>
      <div class="field-row">
        <div class="field">
          <label>画幅</label>
          <select class="select-box" v-model="form.aspect_ratio">
            <option value="16:9">16:9（横屏）</option>
            <option value="9:16">9:16（竖屏）</option>
          </select>
        </div>
        <div class="field">
          <label>FPS</label>
          <input type="number" min="1" max="60" step="1" v-model.number="form.fps" />
        </div>
        <div class="field">
          <label>宽度</label>
          <input type="number" min="256" max="4096" step="8" v-model.number="form.target_width" />
        </div>
        <div class="field">
          <label>高度</label>
          <input type="number" min="256" max="4096" step="8" v-model.number="form.target_height" />
        </div>
      </div>
      <div class="toolbar">
        <button class="pc-primary" :disabled="!canSubmit || creating" @click="handleCreate">
          {{ creating ? "创建中..." : "创建并进入工作台" }}
        </button>
      </div>
    </section>

    <section class="pc-list-header">
      <h2>已有项目</h2>
      <button v-if="!loading" class="ghost-btn" @click="refresh">刷新列表</button>
      <span v-if="!loading" class="helper-text">共 {{ items.length }} 个</span>
    </section>

    <div v-if="loading" class="helper-text">加载中...</div>

    <div v-else-if="!items.length" class="card-shell pc-empty">
      <p>还没有项目，点击右上角「+ 新建项目」开始吧。</p>
    </div>

    <div v-else class="list-grid">
      <article v-for="project in items" :key="project.id" class="item-card pc-project-card">
        <h3>{{ project.name || "未命名项目" }}</h3>
        <p v-if="project.description" class="pc-desc">{{ project.description }}</p>
        <div class="pc-meta helper-text">
          <span>状态：{{ project.status || "DRAFT" }} | Step 解锁：{{ formatStep(project.current_step_unlock) }}</span>
        </div>
        <div class="pc-meta helper-text">
          <span>最近更新时间：{{ formatDate(project.updated_at) }}</span>
        </div>
        <div class="toolbar pc-actions">
          <button class="pc-primary" @click="enterWorkbench(project.id)">进入工作台</button>
          <button class="danger-btn" :disabled="deletingIds.has(project.id)" @click="handleDelete(project)">
            {{ deletingIds.has(project.id) ? "删除中..." : "删除项目" }}
          </button>
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

.danger-btn {
  background: transparent;
  color: #d73a49;
  border-color: #f5c2c7;
}

.danger-btn:hover:not(:disabled) {
  background: #fff5f5;
  border-color: #d73a49;
}

.ghost-btn {
  background: transparent;
  color: #4c3cff;
  border-color: #d7d4ff;
}

.ghost-btn:hover {
  background: #f5f3ff;
}

.field-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 8px;
}

.select-box {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #d4d7e3;
  background: #fff;
  font-size: 14px;
  color: #1f2236;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.select-box:focus {
  border-color: #4c3cff;
  box-shadow: 0 0 0 3px rgba(76, 60, 255, 0.15);
}
</style>
