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

function rebuildSubtitleItems() {
  const overlap = form.transition_enabled ? 0.35 : 0;
  let currentOffset = 0;
  form.subtitle_items = props.segments
    .map((segment) => {
      const video = latestVideo(segment.id);
      if (!video) return null;
      const duration = Number(video.duration_sec || 0);
      const startSec = Number(currentOffset.toFixed(3));
      const endSec = Number((currentOffset + duration).toFixed(3));
      currentOffset += Math.max(duration - overlap, 0);
      const existing = form.subtitle_items.find((item) => item.segment_id === segment.id);
      return {
        segment_id: segment.id,
        seq_no: Number(segment.seq_no || 0),
        scene_name: segment.scene_name || "未命名场景",
        start_sec: existing ? existing.start_sec : startSec,
        end_sec: existing ? existing.end_sec : endSec,
        text: existing ? existing.text : defaultSubtitleText(segment),
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

async function handleExport() {
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

    <div class="list-grid timeline-grid" v-if="form.subtitle_items.length">
      <article v-for="item in form.subtitle_items" :key="item.segment_id" class="item-card">
        <strong>#{{ item.seq_no }} {{ item.scene_name }}</strong>
        <label class="field">
          <span>字幕文本</span>
          <textarea v-model="item.text" class="text-area" rows="4" placeholder="可手动修改导出字幕内容" />
        </label>
        <div class="field-row">
          <label class="field">
            <span>开始秒</span>
            <input v-model="item.start_sec" type="number" min="0" step="0.1" />
          </label>
          <label class="field">
            <span>结束秒</span>
            <input v-model="item.end_sec" type="number" min="0" step="0.1" />
          </label>
        </div>
      </article>
    </div>

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
