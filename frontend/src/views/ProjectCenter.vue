<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { createProject, deleteProject, getProjects } from "../api/projectWorkbench";
import { useToastStore } from "../stores/toast";
import { getErrorMessage } from "../utils/error";

const router = useRouter();
const toast = useToastStore();

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

const GENRE_LABEL_MAP = GENRE_OPTIONS.reduce<Record<string, string>>((acc, cur) => {
  acc[cur.value] = cur.label;
  return acc;
}, {});

const loading = ref(false);
const items = ref<any[]>([]);
const creating = ref(false);
const showCreateForm = ref(true);
const form = ref({
  name: "",
  description: "",
  aspect_ratio: "16:9" as "16:9" | "9:16",
  fps: 24,
  target_width: 1280,
  target_height: 720,
  genre_style: "AUTO" as string,
});
const deletingIds = ref<Set<string>>(new Set());
const confirmDeleteId = ref<string | null>(null);

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
      genre_style: form.value.genre_style || "AUTO",
    });
    const project = res?.data?.data ?? res?.data;
    const projectId = project?.id;
    const styleLabel = GENRE_LABEL_MAP[form.value.genre_style] || form.value.genre_style;
    toast.success(
      `项目「${form.value.name}」已创建（风格=${styleLabel} / ${form.value.aspect_ratio || "16:9"} / ${Number(form.value.fps) || 24}fps / ${Number(form.value.target_width) || 1280}×${Number(form.value.target_height) || 720}）`
    );
    showCreateForm.value = false;
    form.value = {
      name: "",
      description: "",
      aspect_ratio: "16:9",
      fps: 24,
      target_width: 1280,
      target_height: 720,
      genre_style: "AUTO",
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

function cancelDelete(project: any) {
  if (confirmDeleteId.value === project?.id) confirmDeleteId.value = null;
}

function askDelete(project: any) {
  if (!project?.id || deletingIds.value.has(project.id)) return;
  confirmDeleteId.value = project.id;
}

async function confirmDelete(project: any) {
  if (!project?.id || deletingIds.value.has(project.id)) return;
  confirmDeleteId.value = project.id;
  deletingIds.value.add(project.id);
  try {
    const res = await deleteProject(project.id);
    const payload = res?.data?.data ?? res?.data;
    toast.success(
      `已删除项目「${project.name || "未命名项目"}」（删除 ${payload?.deleted_rows ? Object.values(payload.deleted_rows).reduce((a: number, b: number) => a + b, 0) : 0} 条记录，${payload?.deleted_files ?? 0} 个文件）`
    );
    confirmDeleteId.value = null;
    await refresh();
  } catch (error) {
    toast.error(getErrorMessage(error, "删除项目失败"));
  } finally {
    deletingIds.value.delete(project.id);
  }
}

async function handleDelete(project: any) {
  askDelete(project);
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

function genreLabel(value: string | undefined) {
  if (!value) return "未设置";
  return GENRE_LABEL_MAP[value] || value;
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
          <label>短剧风格（资产概念图按此风格生成）</label>
          <select class="select-box" v-model="form.genre_style">
            <option
              v-for="opt in GENRE_OPTIONS"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>
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
      </div>
      <div class="field-row">
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
      <article
        v-for="project in items"
        :key="project.id"
        class="item-card pc-project-card"
        :class="{ 'pc-project-card--danger': confirmDeleteId === project.id }"
      >
        <h3>{{ project.name || "未命名项目" }}</h3>
        <p v-if="project.description" class="pc-desc">{{ project.description }}</p>
        <div class="pc-meta helper-text">
          <span>状态：{{ project.status || "DRAFT" }} | Step 解锁：{{ formatStep(project.current_step_unlock) }} | 风格：{{ genreLabel(project.genre_style) }}</span>
        </div>
        <div class="pc-meta helper-text">
          <span>
            {{ project.aspect_ratio || "16:9" }} /
            {{ project.fps || 24 }}fps /
            {{ project.target_width || 1280 }}×{{ project.target_height || 720 }}
          </span>
        </div>
        <div class="pc-meta helper-text">
          <span>最近更新时间：{{ formatDate(project.updated_at) }}</span>
        </div>

        <div v-if="confirmDeleteId === project.id" class="pc-confirm-delete">
          <p class="pc-confirm-delete__title">确认永久删除项目「{{ project.name || "未命名项目" }}」？</p>
          <p class="pc-confirm-delete__desc helper-text">
            会删除该项目下的资产池、分镜首帧、配音、视频片段、导出成片、任务日志等全部记录与媒体文件，无法撤销。
          </p>
          <div class="toolbar pc-confirm-delete__actions">
            <button class="ghost-btn" :disabled="deletingIds.has(project.id)" @click="cancelDelete(project)">
              取消
            </button>
            <button
              class="danger-btn danger-btn--solid"
              :disabled="deletingIds.has(project.id)"
              @click="confirmDelete(project)"
            >
              {{ deletingIds.has(project.id) ? "删除中..." : "确认永久删除" }}
            </button>
          </div>
        </div>

        <div v-else class="toolbar pc-actions">
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

.danger-btn--solid {
  background: #d73a49;
  color: #fff;
  border-color: #d73a49;
  font-weight: 600;
}

.danger-btn--solid:hover:not(:disabled) {
  background: #b82f3c;
  border-color: #b82f3c;
}

.pc-project-card--danger {
  border-color: #f5c2c7;
  background: linear-gradient(180deg, #fff5f5 0%, #ffffff 100%);
}

.pc-confirm-delete {
  margin-top: 8px;
  padding: 12px 14px;
  border: 1px dashed #f5c2c7;
  border-radius: 10px;
  background: #fffafa;
}

.pc-confirm-delete__title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: #8a1b27;
}

.pc-confirm-delete__desc {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
}

.pc-confirm-delete__actions {
  justify-content: flex-end;
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
