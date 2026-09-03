<script setup lang="ts">
import { generateFrame, lockFrame } from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  segments: any[];
  frames: any[];
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();

function latestFrame(segmentId: string) {
  return props.frames
    .filter((item) => item.segment_id === segmentId)
    .sort((a, b) => Number(b.version_no || 0) - Number(a.version_no || 0))[0];
}

async function handleGenerate(segmentId: string) {
  try {
    await generateFrame(segmentId, {
      width: 1280,
      height: 720,
      prompt_override: "",
      negative_prompt_override: "",
    });
    toast.success("首帧已提交生成");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "生成首帧失败"));
  }
}

async function handleLock(frameId: string) {
  try {
    await lockFrame(frameId, true);
    toast.success("已锁定首帧");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "锁帧失败"));
  }
}
</script>

<template>
  <section class="step-view">
    <h2>Step 3 九宫格与首帧锁定</h2>

    <div class="list-grid" v-if="segments.length">
      <article v-for="segment in segments" :key="segment.id" class="item-card">
        <strong>#{{ segment.seq_no }} {{ segment.scene_name || "未命名场景" }}</strong>
        <p>{{ segment.visual_desc }}</p>

        <img
          v-if="latestFrame(segment.id)?.image_url"
          :src="`http://127.0.0.1:8000${latestFrame(segment.id).image_url}`"
          class="preview-image"
          alt="frame"
        />

        <p v-if="latestFrame(segment.id)">状态：{{ latestFrame(segment.id).is_locked ? "已锁定" : "未锁定" }}</p>

        <div class="toolbar">
          <button @click="handleGenerate(segment.id)">生成首帧</button>
          <button v-if="latestFrame(segment.id)" @click="handleLock(latestFrame(segment.id).id)">锁定首帧</button>
        </div>
      </article>
    </div>
  </section>
</template>
