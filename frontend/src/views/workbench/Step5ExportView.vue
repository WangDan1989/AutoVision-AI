<script setup lang="ts">
import { reactive, computed, ref, watch } from "vue";

import { generateAudio, generateExport, generateVideo } from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  segments: any[];
  videos: any[];
  audioTracks: any[];
  exportsList: any[];
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();
const submitting = ref(false);
const previewTime = ref(0);
const quickRunRunning = ref(false);
const quickRunProgress = ref({ phase: "idle", done: 0, total: 0, success: 0, failed: 0 });
const quickRunFailures = ref<Array<{ label: string; message: string }>>([]);
const DEFAULT_TRANSITION_SEC = 0.35;
const form = reactive({
  subtitle_enabled: true,
  transition_enabled: true,
  subtitle_items: [] as Array<{
    segment_id: string;
    seq_no: number;
    scene_name: string;
    start_sec: number;
    end_sec: number;
    text: string;
  }>,
});

function latestVideo(segmentId: string) {
  return props.videos
    .filter((item) => item.segment_id === segmentId)
    .sort((a, b) => Number(b.version_no || 0) - Number(a.version_no || 0))[0];
}

function segmentLabel(segmentId: string) {
  const segment = props.segments.find((item) => item.id === segmentId);
  if (!segment) return segmentId;
  return `#${segment.seq_no} ${segment.scene_name || "未命名场景"}`;
}

function formatTimeRange(startSec: number, endSec: number) {
  return `${formatSeconds(startSec)} - ${formatSeconds(endSec)}`;
}

function summaryStats(item: any) {
  const composePlan = item.compose_plan || [];
  const audioCount = composePlan.filter((plan: any) => !!plan.audio_track_id).length;
  const subtitleCount = composePlan.filter((plan: any) => !!String(plan.subtitle_text || "").trim()).length;
  return {
    segments: composePlan.length,
    audioCount,
    subtitleCount,
  };
}

const latestExportItem = computed(() => props.exportsList[0] || null);

function defaultSubtitleText(segment: any) {
  return [segment.dialogue_text || "", segment.narration_text || ""].filter(Boolean).join("\n");
}

function formatSeconds(seconds: number) {
  const safeValue = Math.max(Number(seconds || 0), 0);
  return `${safeValue.toFixed(1)}s`;
}

function rebuildSubtitleItems(preserveExisting = true) {
  const overlap = form.transition_enabled ? DEFAULT_TRANSITION_SEC : 0;
  const existingMap = new Map(form.subtitle_items.map((item) => [item.segment_id, item]));
  let currentOffset = 0;
  form.subtitle_items = props.segments
    .map((segment) => {
      const video = latestVideo(segment.id);
      if (!video) return null;
      const duration = Number(video.duration_sec || 0);
      const startSec = Number(currentOffset.toFixed(3));
      const endSec = Number((currentOffset + duration).toFixed(3));
      currentOffset += Math.max(duration - overlap, 0);
      const existing = existingMap.get(segment.id);
      return {
        segment_id: segment.id,
        seq_no: Number(segment.seq_no || 0),
        scene_name: segment.scene_name || "未命名场景",
        start_sec: preserveExisting && existing ? existing.start_sec : startSec,
        end_sec: preserveExisting && existing ? existing.end_sec : endSec,
        text: preserveExisting && existing ? existing.text : defaultSubtitleText(segment),
      };
    })
    .filter(Boolean) as Array<{
      segment_id: string;
      seq_no: number;
      scene_name: string;
      start_sec: number;
      end_sec: number;
      text: string;
    }>;
}

watch(
  () => [props.segments, props.videos, form.transition_enabled],
  () => {
    rebuildSubtitleItems();
  },
  { immediate: true, deep: true },
);

const readyCount = computed(() =>
  props.segments.filter((segment) => props.videos.some((video) => video.segment_id === segment.id)).length,
);

const sortedSubtitleItems = computed(() =>
  [...form.subtitle_items].sort((a, b) => Number(a.start_sec || 0) - Number(b.start_sec || 0)),
);

const missingVideoSegments = computed(() =>
  props.segments.filter((segment) => !latestVideo(segment.id)),
);

const emptySubtitleItems = computed(() =>
  form.subtitle_enabled
    ? form.subtitle_items.filter((item) => !String(item.text || "").trim())
    : [],
);

const reversedSubtitleItems = computed(() =>
  form.subtitle_items.filter((item) => Number(item.end_sec || 0) < Number(item.start_sec || 0)),
);

const overlapPairs = computed(() => {
  const pairs: Array<{
    currentId: string;
    nextId: string;
    currentLabel: string;
    nextLabel: string;
  }> = [];
  for (let index = 0; index < sortedSubtitleItems.value.length - 1; index += 1) {
    const current = sortedSubtitleItems.value[index];
    const next = sortedSubtitleItems.value[index + 1];
    if (Number(next.start_sec || 0) < Number(current.end_sec || 0)) {
      pairs.push({
        currentId: current.segment_id,
        nextId: next.segment_id,
        currentLabel: `#${current.seq_no} ${current.scene_name}`,
        nextLabel: `#${next.seq_no} ${next.scene_name}`,
      });
    }
  }
  return pairs;
});

const issueMap = computed(() => {
  const map = new Map<string, string[]>();
  for (const item of emptySubtitleItems.value) {
    map.set(item.segment_id, [...(map.get(item.segment_id) || []), "字幕为空"]);
  }
  for (const item of reversedSubtitleItems.value) {
    map.set(item.segment_id, [...(map.get(item.segment_id) || []), "结束时间早于开始时间"]);
  }
  for (const pair of overlapPairs.value) {
    map.set(pair.currentId, [...(map.get(pair.currentId) || []), "与下一条字幕时间重叠"]);
    map.set(pair.nextId, [...(map.get(pair.nextId) || []), "与上一条字幕时间重叠"]);
  }
  return map;
});

const precheckItems = computed(() => {
  const checks: Array<{ level: "error" | "warning"; text: string }> = [];
  for (const segment of missingVideoSegments.value) {
    checks.push({
      level: "error",
      text: `分镜 #${segment.seq_no} ${segment.scene_name || "未命名场景"} 缺少视频片段`,
    });
  }
  for (const item of emptySubtitleItems.value) {
    checks.push({
      level: "error",
      text: `分镜 #${item.seq_no} ${item.scene_name} 的字幕文本为空`,
    });
  }
  for (const item of reversedSubtitleItems.value) {
    checks.push({
      level: "error",
      text: `分镜 #${item.seq_no} ${item.scene_name} 的字幕结束时间早于开始时间`,
    });
  }
  for (const pair of overlapPairs.value) {
    checks.push({
      level: "warning",
      text: `${pair.currentLabel} 与 ${pair.nextLabel} 的字幕时间重叠`,
    });
  }
  return checks;
});

const blockingPrecheckItems = computed(() =>
  precheckItems.value.filter((item) => item.level === "error"),
);

const totalPreviewDuration = computed(() =>
  sortedSubtitleItems.value.reduce((maxValue, item) => Math.max(maxValue, Number(item.end_sec || 0)), 0),
);

const activePreviewItems = computed(() =>
  sortedSubtitleItems.value.filter((item) => {
    const startSec = Number(item.start_sec || 0);
    const endSec = Number(item.end_sec || 0);
    return previewTime.value >= startSec && previewTime.value <= endSec;
  }),
);

watch(totalPreviewDuration, (value) => {
  if (previewTime.value > value) {
    previewTime.value = Math.max(value, 0);
  }
});

function resetTimeline() {
  rebuildSubtitleItems(false);
  toast.success("字幕时间轴已按片段时长重置");
}

function resetSubtitleText() {
  form.subtitle_items = form.subtitle_items.map((item) => {
    const segment = props.segments.find((segmentItem) => segmentItem.id === item.segment_id);
    return {
      ...item,
      text: segment ? defaultSubtitleText(segment) : item.text,
    };
  });
  toast.success("字幕文本已恢复为自动生成内容");
}

function applyExportPlanToForm(exportItem: any) {
  if (!exportItem) {
    toast.error("当前还没有可复用的导出方案");
    return;
  }

  form.subtitle_enabled = !!exportItem.subtitle_enabled;
  form.transition_enabled = !!exportItem.transition_enabled;

  const planMap = new Map(
    (exportItem.compose_plan || []).map((plan: any) => [plan.segment_id, plan]),
  );

  form.subtitle_items = props.segments
    .map((segment) => {
      const plan = planMap.get(segment.id);
      if (!plan) return null;
      return {
        segment_id: segment.id,
        seq_no: Number(segment.seq_no || 0),
        scene_name: segment.scene_name || "未命名场景",
        start_sec: Number(plan.subtitle_start_sec || plan.start_sec || 0),
        end_sec: Number(plan.subtitle_end_sec || plan.end_sec || 0),
        text: String(plan.subtitle_text || ""),
      };
    })
    .filter(Boolean) as Array<{
      segment_id: string;
      seq_no: number;
      scene_name: string;
      start_sec: number;
      end_sec: number;
      text: string;
    }>;

  toast.success(`已载入导出版本 v${exportItem.version_no} 的方案`);
}

function exportPayload() {
  return {
    subtitle_enabled: form.subtitle_enabled,
    transition_enabled: form.transition_enabled,
    subtitle_items: form.subtitle_items.map((item) => ({
      segment_id: item.segment_id,
      start_sec: Number(item.start_sec || 0),
      end_sec: Number(item.end_sec || 0),
      text: item.text || "",
    })),
  };
}

function defaultVideoPayload() {
  return {
    duration_sec: 3,
    fps: 24,
    width: 1280,
    height: 720,
  };
}

function defaultAudioPayload() {
  return {
    track_type: "NARRATION",
    voice_profile: "",
    text_content: "",
  };
}

function issuesOf(segmentId: string) {
  return issueMap.value.get(segmentId) || [];
}

async function handleExport() {
  if (blockingPrecheckItems.value.length) {
    toast.error("请先修复导出预检中的错误项");
    return;
  }
  const invalidItem = form.subtitle_items.find((item) => Number(item.end_sec || 0) < Number(item.start_sec || 0));
  if (invalidItem) {
    toast.error(`分镜 #${invalidItem.seq_no} 的字幕结束时间不能早于开始时间`);
    return;
  }
  submitting.value = true;
  try {
    await generateExport(props.projectId, exportPayload());
    toast.success("成片已导出");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "导出失败"));
  } finally {
    submitting.value = false;
  }
}

async function handleReExportLatest() {
  if (!latestExportItem.value) {
    toast.error("当前还没有历史导出可复用");
    return;
  }
  applyExportPlanToForm(latestExportItem.value);

  if (blockingPrecheckItems.value.length) {
    toast.error("最近导出方案存在当前不可通过的预检项，请先修正");
    return;
  }

  submitting.value = true;
  try {
    await generateExport(props.projectId, exportPayload());
    toast.success(`已按导出版本 v${latestExportItem.value.version_no} 的方案重新导出`);
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "重新导出失败"));
  } finally {
    submitting.value = false;
  }
}

async function handleQuickRunPipeline() {
  if (!props.segments.length) {
    toast.error("当前项目还没有可处理的分镜");
    return;
  }

  quickRunRunning.value = true;
  quickRunFailures.value = [];

  const missingVideoItems = props.segments.filter((segment) => !latestVideo(segment.id));
  quickRunProgress.value = {
    phase: "补齐视频",
    done: 0,
    total: missingVideoItems.length,
    success: 0,
    failed: 0,
  };

  for (const segment of missingVideoItems) {
    try {
      await generateVideo(segment.id, defaultVideoPayload());
      quickRunProgress.value.success += 1;
    } catch (error) {
      quickRunProgress.value.failed += 1;
      quickRunFailures.value.push({
        label: `视频 #${segment.seq_no} ${segment.scene_name || "未命名场景"}`,
        message: getErrorMessage(error, "生成视频失败"),
      });
    } finally {
      quickRunProgress.value.done += 1;
    }
  }

  const missingAudioItems = props.segments.filter((segment) => !props.audioTracks.some((item) => item.segment_id === segment.id));
  quickRunProgress.value = {
    phase: "补齐音频",
    done: 0,
    total: missingAudioItems.length,
    success: 0,
    failed: quickRunProgress.value.failed,
  };

  for (const segment of missingAudioItems) {
    try {
      await generateAudio(segment.id, defaultAudioPayload());
      quickRunProgress.value.success += 1;
    } catch (error) {
      quickRunProgress.value.failed += 1;
      quickRunFailures.value.push({
        label: `音频 #${segment.seq_no} ${segment.scene_name || "未命名场景"}`,
        message: getErrorMessage(error, "生成音频失败"),
      });
    } finally {
      quickRunProgress.value.done += 1;
    }
  }

  quickRunProgress.value = {
    phase: "导出成片",
    done: 0,
    total: 1,
    success: 0,
    failed: quickRunProgress.value.failed,
  };

  try {
    await generateExport(props.projectId, exportPayload());
    quickRunProgress.value.success = 1;
    quickRunProgress.value.done = 1;
    toast.success("已完成补齐素材并导出");
    emit("refresh");
  } catch (error) {
    quickRunProgress.value.failed += 1;
    quickRunProgress.value.done = 1;
    quickRunFailures.value.push({
      label: "导出成片",
      message: getErrorMessage(error, "导出失败"),
    });
    toast.error(getErrorMessage(error, "一键补齐并导出失败"));
  } finally {
    quickRunRunning.value = false;
  }
}
</script>

<template>
  <section class="step-view">
    <div class="toolbar toolbar-between">
      <div>
        <h2>Step 5 合成导出</h2>
        <p>已具备视频分镜：{{ readyCount }}/{{ segments.length }}</p>
      </div>
      <button :disabled="submitting || quickRunRunning || !segments.length || readyCount < segments.length || blockingPrecheckItems.length > 0" @click="handleExport">
        开始导出
      </button>
    </div>

    <div class="quick-run-panel">
      <div class="toolbar">
        <button type="button" :disabled="submitting || quickRunRunning || !segments.length" @click="handleQuickRunPipeline">
          一键补齐素材并导出
        </button>
        <span class="helper-text">会按顺序补齐缺失视频、缺失音频，然后直接导出</span>
      </div>
      <p v-if="quickRunRunning || quickRunProgress.phase !== 'idle'" class="quick-run-progress">
        当前阶段：{{ quickRunProgress.phase }}，进度 {{ quickRunProgress.done }}/{{ quickRunProgress.total }}，成功 {{ quickRunProgress.success }}，失败 {{ quickRunProgress.failed }}
      </p>
      <div v-if="quickRunFailures.length" class="quick-run-failures">
        <strong>本轮快捷流程失败项</strong>
        <p v-for="item in quickRunFailures" :key="`${item.label}-${item.message}`" class="quick-run-failure-item">
          {{ item.label }}：{{ item.message }}
        </p>
      </div>
    </div>

    <div class="toolbar" v-if="latestExportItem">
      <button type="button" :disabled="submitting" @click="applyExportPlanToForm(latestExportItem)">
        载入最近导出方案
      </button>
      <button type="button" :disabled="submitting || quickRunRunning || !segments.length" @click="handleReExportLatest">
        按最近方案重导
      </button>
      <span class="helper-text">当前最近版本：v{{ latestExportItem.version_no }}</span>
    </div>

    <div class="form-grid">
      <label class="field-inline">
        <input v-model="form.subtitle_enabled" type="checkbox" />
        <span>烧录字幕到成片</span>
      </label>
      <label class="field-inline">
        <input v-model="form.transition_enabled" type="checkbox" />
        <span>启用片段淡入淡出转场</span>
      </label>
    </div>

    <div class="toolbar">
      <button type="button" @click="resetTimeline">一键重置时间轴</button>
      <button type="button" @click="resetSubtitleText">恢复默认字幕</button>
    </div>

    <section class="precheck-card">
      <div class="toolbar toolbar-between">
        <strong>导出预检</strong>
        <span>{{ precheckItems.length ? `发现 ${precheckItems.length} 项问题` : "未发现问题" }}</span>
      </div>
      <div v-if="precheckItems.length" class="precheck-list">
        <p
          v-for="(item, index) in precheckItems"
          :key="`${item.level}-${index}`"
          class="precheck-item"
          :class="item.level === 'error' ? 'precheck-error' : 'precheck-warning'"
        >
          {{ item.text }}
        </p>
      </div>
      <p v-else class="precheck-ok">当前导出参数可直接提交。</p>
    </section>

    <div class="list-grid timeline-grid" v-if="form.subtitle_items.length">
      <article
        v-for="item in form.subtitle_items"
        :key="item.segment_id"
        class="item-card"
        :class="{ 'item-card-error': issuesOf(item.segment_id).length > 0 }"
      >
        <strong>#{{ item.seq_no }} {{ item.scene_name }}</strong>
        <p>当前片段默认时间：{{ formatSeconds(item.start_sec) }} - {{ formatSeconds(item.end_sec) }}</p>
        <div v-if="issuesOf(item.segment_id).length" class="inline-issue-list">
          <p v-for="issue in issuesOf(item.segment_id)" :key="issue" class="inline-issue-item">
            {{ issue }}
          </p>
        </div>
        <label class="field">
          <span>字幕文本</span>
          <textarea v-model="item.text" class="text-area" rows="4" placeholder="可手动修改导出字幕内容" />
        </label>
        <div class="field-row">
          <label class="field">
            <span>开始秒</span>
            <input v-model.number="item.start_sec" type="number" min="0" step="0.1" />
          </label>
          <label class="field">
            <span>结束秒</span>
            <input v-model.number="item.end_sec" type="number" min="0" step="0.1" />
          </label>
        </div>
      </article>
    </div>

    <section v-if="sortedSubtitleItems.length" class="subtitle-preview-card">
      <div class="toolbar toolbar-between">
        <strong>导出前字幕预览</strong>
        <span>{{ formatSeconds(previewTime) }} / {{ formatSeconds(totalPreviewDuration) }}</span>
      </div>
      <input
        v-model.number="previewTime"
        class="timeline-slider"
        type="range"
        min="0"
        :max="Math.max(totalPreviewDuration, 0)"
        step="0.1"
      />
      <div class="subtitle-stage">
        <p v-if="!activePreviewItems.length" class="subtitle-empty">当前时刻没有字幕</p>
        <p v-for="item in activePreviewItems" :key="item.segment_id" class="subtitle-line">
          {{ item.text || "空字幕" }}
        </p>
      </div>
      <div class="subtitle-list">
        <article
          v-for="item in sortedSubtitleItems"
          :key="item.segment_id"
          class="subtitle-list-item"
          :class="{ active: previewTime >= Number(item.start_sec || 0) && previewTime <= Number(item.end_sec || 0) }"
        >
          <strong>#{{ item.seq_no }} {{ item.scene_name }}</strong>
          <p>{{ formatSeconds(item.start_sec) }} - {{ formatSeconds(item.end_sec) }}</p>
          <p class="subtitle-text-preview">{{ item.text || "空字幕" }}</p>
        </article>
      </div>
    </section>

    <div class="list-grid" v-if="exportsList.length">
      <article v-for="item in exportsList" :key="item.id" class="item-card">
        <strong>导出版本 v{{ item.version_no }}</strong>
        <p>状态：{{ item.status }}</p>
        <p>片段数：{{ summaryStats(item).segments }}</p>
        <p>音轨数：{{ summaryStats(item).audioCount }}，字幕段数：{{ summaryStats(item).subtitleCount }}</p>
        <p>字幕：{{ item.subtitle_enabled ? "已烧录" : "未烧录" }}，转场：{{ item.transition_enabled ? "已启用" : "未启用" }}</p>
        <video v-if="item.output_url" class="preview-media" controls :src="`http://127.0.0.1:8000${item.output_url}`" />
        <a v-if="item.output_url" :href="`http://127.0.0.1:8000${item.output_url}`" target="_blank" rel="noreferrer">打开成片</a>

        <div v-if="(item.compose_plan || []).length" class="compose-plan-list">
          <article v-for="plan in item.compose_plan" :key="`${item.id}-${plan.segment_id}`" class="compose-plan-item">
            <strong>{{ segmentLabel(plan.segment_id) }}</strong>
            <p>时间轴：{{ formatTimeRange(Number(plan.start_sec || 0), Number(plan.end_sec || 0)) }}</p>
            <p>视频片段：{{ plan.video_clip_id || "无" }}</p>
            <p>音频片段：{{ plan.audio_track_id || "无" }}</p>
            <p v-if="plan.subtitle_text">字幕：{{ plan.subtitle_text }}</p>
            <p v-if="plan.subtitle_text">
              字幕时间：{{ formatTimeRange(Number(plan.subtitle_start_sec || 0), Number(plan.subtitle_end_sec || 0)) }}
            </p>
            <p v-else>字幕：无</p>
          </article>
        </div>
      </article>
    </div>
  </section>
</template>
