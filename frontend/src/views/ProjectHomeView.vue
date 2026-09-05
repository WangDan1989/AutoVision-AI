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
const confirmDeleteId = ref<string | null>(null);
const projects = ref<any[]>([]);

const GENRE_OPTIONS = [
  { value: "AUTO", label: "自动识别（剧本自动匹配）" },
  { value: "GUZHUANG_XIANXIA", label: "古装仙侠" },
  { value: "GUZHUANG_WUXIA", label: "古装武侠" },
  { value: "GUFENG_ZHAIDOU", label: "古风宅斗" },
  { value: "XIANDAN_DUSHI", label: "现代都市" },
  { value: "XIAOYUAN_QINGCHUN", label: "校园青春" },
  { value: "XUANYI_TUILI", label: "悬疑推理" },
  { value: "MINGUO_DIEZHAN", label: "民国谍战" },
  { value: "KEHUAN_MOSHI", label: "科幻末世" },
  { value: "ZHICHANG_JINGYING", label: "职场经营" },
  { value: "JIATING_LUNLI", label: "家庭伦理" },
  { value: "KAIXIAO_WENNAN", label: "爆笑微甜" },
] as const;

const GENRE_LABEL_MAP: Record<string, string> = GENRE_OPTIONS.reduce(
  (acc, cur) => {
    acc[cur.value] = cur.label;
    return acc;
  },
  {} as Record<string, string>,
);

const form = reactive({
  name: "",
  description: "",
  aspect_ratio: "16:9" as "16:9" | "9:16",
  target_width: 1280,
  target_height: 720,
  fps: 24,
  genre_style: "AUTO" as string,
});

const hasProjects = computed(() => projects.value.length > 0);

function genreLabel(v: string | undefined) {
  if (!v) return "未设置";
  return GENRE_LABEL_MAP[v] || v;
}

function formatDate(v: string | undefined) {
  if (!v) return "-";
  try {
    return new Date(v).toLocaleString();
  } catch {
    return v;
  }
}

function formatStep(u: number | undefined) {
  const stepNames = ["", "1. 剧本拆解", "2. 资产池", "3. 分镜首帧", "4. 音频与视频", "5. 导出成片"];
  return stepNames[u ?? 1] || stepNames[1];
}

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
      genre_style: form.genre_style || "AUTO",
    });
    const projectId = response.data.data.id;
    const sl = GENRE_LABEL_MAP[form.genre_style] || form.genre_style;
    toast.success(`项目「${form.name}」已创建（风格=${sl} / ${form.aspect_ratio} / ${Number(form.fps)}fps / ${Number(form.target_width)}×${Number(form.target_height)}）`);
    form.name = "";
    form.description = "";
    form.aspect_ratio = "16:9";
    form.fps = 24;
    form.target_width = 1280;
    form.target_height = 720;
    form.genre_style = "AUTO";
    await loadProjects();
    router.push(`/projects/${projectId}/workbench`);
  } catch (error) {
    toast.error(getErrorMessage(error, "创建项目失败"));
  } finally {
    creating.value = false;
  }
}

function cancelDelete() {
  confirmDeleteId.value = null;
}

function askDelete(project: any) {
  if (!project?.id || deletingId.value === project.id) return;
  confirmDeleteId.value = project.id;
}

async function confirmDelete(project: any) {
  if (!project?.id) return;
  deletingId.value = project.id;
  try {
    const res = await deleteProject(project.id);
    const payload = res?.data?.data ?? res?.data;
    const deletedRecords = payload?.deleted_rows
      ? Object.values(payload.deleted_rows).reduce((a: number, b: any) => a + Number(b || 0), 0)
      : 0;
    const deletedFiles = payload?.deleted_files ?? 0;
    toast.success(
      `项目「${project.name}」已永久删除（${deletedRecords} 条记录 / ${deletedFiles} 个文件）`
    );
    confirmDeleteId.value = null;
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
          <input v-model="form.name" type="text" placeholder="例如：都市夜景短剧" maxlength="64" />
        </label>
        <label class="field">
          <span>项目描述</span>
          <input v-model="form.description" type="text" placeholder="可选，用于备注本次项目目标" />
        </label>
        <div class="field-row field-row--3">
          <label class="field">
            <span>短剧风格（资产概念图按此风格生成）</span>
            <select v-model="form.genre_style">
              <option
                v-for="opt in GENRE_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>画幅</span>
            <select v-model="form.aspect_ratio">
              <option value="16:9">16:9（横屏）</option>
              <option value="9:16">9:16（竖屏）</option>
            </select>
          </label>
          <label class="field">
            <span>FPS</span>
            <input v-model.number="form.fps" type="number" min="1" max="60" step="1" />
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span>宽度</span>
            <input v-model.number="form.target_width" type="number" min="256" max="4096" step="8" />
          </label>
          <label class="field">
            <span>高度</span>
            <input v-model.number="form.target_height" type="number" min="256" max="4096" step="8" />
          </label>
        </div>
      </div>
      <div class="toolbar">
        <button class="primary-btn" :disabled="!form.name.trim() || creating" @click="handleCreateProject">
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
        <button class="ghost-btn" :disabled="loading" @click="loadProjects">
          {{ loading ? "刷新中..." : "刷新列表" }}
        </button>
      </div>

      <div v-if="hasProjects" class="list-grid">
        <article
          v-for="project in projects"
          :key="project.id"
          class="item-card home-item"
          :class="{ 'is-confirm-delete': confirmDeleteId === project.id }"
        >
          <h3>{{ project.name || "未命名项目" }}</h3>
          <p v-if="project.description" class="item-desc">{{ project.description }}</p>
          <p class="helper-text">
            状态：{{ project.status || "DRAFT" }} | Step 解锁：{{ formatStep(project.current_step_unlock) }} | 风格：{{ genreLabel(project.genre_style) }}
          </p>
          <p class="helper-text">
            {{ project.aspect_ratio || "16:9" }} / {{ project.fps || 24 }}fps / {{ project.target_width || 1280 }}×{{ project.target_height || 720 }}
          </p>
          <p class="helper-text">最近更新时间：{{ formatDate(project.updated_at) }}</p>

          <div v-if="confirmDeleteId === project.id" class="confirm-delete-panel">
            <p class="confirm-delete__title">确认永久删除项目「{{ project.name || "未命名项目" }}」？</p>
            <p class="helper-text confirm-delete__desc">
              会同时删除该项目下的资产池、分镜首帧、配音、视频片段、导出成片、任务日志等全部记录与媒体文件，操作不可撤销。
            </p>
            <div class="toolbar confirm-delete__actions">
              <button class="ghost-btn" :disabled="deletingId === project.id" @click="cancelDelete">取消</button>
              <button
                class="danger-btn danger-btn--solid"
                :disabled="deletingId === project.id"
                @click="confirmDelete(project)"
              >
                {{ deletingId === project.id ? "删除中..." : "确认永久删除" }}
              </button>
            </div>
          </div>

          <div v-else class="toolbar">
            <button class="primary-btn" @click="openWorkbench(project.id)">进入工作台</button>
            <button
              class="danger-btn"
              :disabled="deletingId === project.id"
              @click="askDelete(project)"
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

<style scoped>
.project-home {
  padding: 28px 40px 60px;
  max-width: 1280px;
  margin: 0 auto;
}

.project-create-card {
  margin-bottom: 24px;
}

.project-create-card h2,
.project-list-card h2 {
  margin: 0 0 16px;
  font-size: 20px;
}

.form-grid {
  display: grid;
  gap: 14px;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.field-row--3 {
  grid-template-columns: repeat(3, 1fr);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field > span {
  font-size: 13px;
  color: #4b5069;
  font-weight: 500;
}

.field input,
.field select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #d4d7e3;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  color: #1d1f2c;
  outline: none;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}

.field input:focus,
.field select:focus {
  border-color: #6b5bff;
  box-shadow: 0 0 0 3px rgba(107, 91, 255, 0.14);
}

.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
}

.toolbar-between {
  justify-content: space-between;
  margin-top: 0;
}

button {
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid #d4d7e3;
  background: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease, opacity 120ms ease;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.primary-btn {
  background: #4c3cff;
  border-color: #4c3cff;
  color: #fff;
}

.primary-btn:hover:not(:disabled) {
  background: #3f31e0;
  border-color: #3f31e0;
}

.ghost-btn {
  background: #f5f6fb;
  border-color: #e1e4ef;
  color: #3b3f58;
}

.ghost-btn:hover:not(:disabled) {
  background: #eceeff;
}

.danger-btn {
  background: #fff;
  border-color: #ffb4b4;
  color: #d0342c;
}

.danger-btn:hover:not(:disabled) {
  background: #fff1f0;
}

.danger-btn--solid {
  background: #d0342c;
  border-color: #d0342c;
  color: #fff;
}

.danger-btn--solid:hover:not(:disabled) {
  background: #b92c25;
  border-color: #b92c25;
}

.list-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.item-desc {
  margin: 2px 0 6px;
  font-size: 13px;
  color: #5a5f73;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.home-item {
  position: relative;
}

.home-item.is-confirm-delete {
  border-color: #ff9c94;
  box-shadow: 0 0 0 3px rgba(255, 92, 84, 0.14);
}

.confirm-delete-panel {
  margin-top: 8px;
  padding: 12px;
  border-radius: 10px;
  background: #fff4f3;
  border: 1px dashed #ffb4b4;
}

.confirm-delete__title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: #b92c25;
}

.confirm-delete__desc {
  margin: 0 0 8px;
  line-height: 1.5;
}

.confirm-delete__actions {
  margin-top: 0;
  justify-content: flex-end;
}
</style>
