<script setup lang="ts">
import { reactive, computed, ref, watch } from "vue";

import { generateExport } from "../../api/projectWorkbench";
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

async function handleExport() {
  const invalidItem = form.subtitle_items.find((item) => Number(item.end_sec || 0) < Number(item.start_sec || 0));
  if (invalidItem) {
    toast.error(`分镜 #${invalidItem.seq_no} 的字幕结束时间不能早于开始时间`);
    return;
  }
  submitting.value = true;
  try {
    await generateExport(props.projectId, {
      subtitle_enabled: form.subtitle_enabled,
      transition_enabled: form.transition_enabled,
      subtitle_items: form.subtitle_items.map((item) => ({
        segment_id: item.segment_id,
        start_sec: Number(item.start_sec || 0),
        end_sec: Number(item.end_sec || 0),
        text: item.text || "",
      })),
    });
    toast.success("成片已导出");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "导出失败"));
  } finally {
    submitting.value = false;
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
      <button :disabled="submitting || !segments.length || readyCount < segments.length" @click="handleExport">开始导出</button>
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

    <div class="list-grid timeline-grid" v-if="form.subtitle_items.length">
      <article v-for="item in form.subtitle_items" :key="item.segment_id" class="item-card">
        <strong>#{{ item.seq_no }} {{ item.scene_name }}</strong>
        <p>当前片段默认时间：{{ formatSeconds(item.start_sec) }} - {{ formatSeconds(item.end_sec) }}</p>
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
        <p>片段数：{{ (item.compose_plan || []).length }}</p>
        <video v-if="item.output_url" class="preview-media" controls :src="`http://127.0.0.1:8000${item.output_url}`" />
        <a v-if="item.output_url" :href="`http://127.0.0.1:8000${item.output_url}`" target="_blank" rel="noreferrer">打开成片</a>
      </article>
    </div>
  </section>
</template>
