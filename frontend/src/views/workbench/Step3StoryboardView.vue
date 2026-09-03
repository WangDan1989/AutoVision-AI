<script setup lang="ts">
import { reactive, watch } from "vue";

import { generateFrame, lockFrame, updateProjectPreferences } from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  project: any;
  segments: any[];
  frames: any[];
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();
const form = reactive({
  prompt_override: "",
  negative_prompt_override: "",
  width: 1280,
  height: 720,
});
let hydrating = false;
let saveTimer: ReturnType<typeof setTimeout> | null = null;

function defaultMediaPrefs() {
  return props.project?.preferences?.media || {
    video_duration_sec: 3,
    video_fps: props.project?.fps || 24,
    video_width: props.project?.target_width || 1280,
    video_height: props.project?.target_height || 720,
    audio_track_type: "NARRATION",
    audio_voice_profile: "",
  };
}

function defaultExportPrefs() {
  return props.project?.preferences?.export || {
    subtitle_enabled: true,
    transition_enabled: true,
  };
}

watch(
  () => props.project?.preferences?.storyboard,
  (value) => {
    hydrating = true;
    form.prompt_override = value?.prompt_override || "";
    form.negative_prompt_override = value?.negative_prompt_override || "";
    form.width = Number(value?.width || props.project?.target_width || 1280);
    form.height = Number(value?.height || props.project?.target_height || 720);
    hydrating = false;
  },
  { immediate: true, deep: true },
);

watch(
  form,
  () => {
    if (hydrating || !props.project) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try {
        await updateProjectPreferences(props.projectId, {
          storyboard: { ...form },
          media: defaultMediaPrefs(),
          export: defaultExportPrefs(),
        });
      } catch {
        // keep local form usable even if persistence fails
      }
    }, 400);
  },
  { deep: true },
);

function latestFrame(segmentId: string) {
  return props.frames
    .filter((item) => item.segment_id === segmentId)
    .sort((a, b) => Number(b.version_no || 0) - Number(a.version_no || 0))[0];
}

async function handleGenerate(segmentId: string) {
  try {
    await generateFrame(segmentId, {
      width: Number(form.width || 1280),
      height: Number(form.height || 720),
      prompt_override: form.prompt_override,
      negative_prompt_override: form.negative_prompt_override,
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

    <div class="form-grid">
      <label class="field">
        <span>全局正向补充提示词</span>
        <textarea v-model="form.prompt_override" class="text-area" rows="3" placeholder="会追加到每次首帧生成的提示词中" />
      </label>
      <label class="field">
        <span>全局反向提示词</span>
        <textarea v-model="form.negative_prompt_override" class="text-area" rows="3" placeholder="如 low quality, blurry" />
      </label>
      <label class="field">
        <span>宽度</span>
        <input v-model.number="form.width" type="number" min="256" step="64" />
      </label>
      <label class="field">
        <span>高度</span>
        <input v-model.number="form.height" type="number" min="256" step="64" />
      </label>
    </div>

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
