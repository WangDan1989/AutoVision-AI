<script setup lang="ts">
import { reactive, computed, ref } from "vue";

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
});

const readyCount = computed(() =>
  props.segments.filter((segment) => props.videos.some((video) => video.segment_id === segment.id)).length,
);

async function handleExport() {
  submitting.value = true;
  try {
    await generateExport(props.projectId, form);
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
        <span>保留字幕开关（当前仅入库，未烧录）</span>
      </label>
      <label class="field-inline">
        <input v-model="form.transition_enabled" type="checkbox" />
        <span>保留转场开关（当前按顺序硬拼接）</span>
      </label>
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
