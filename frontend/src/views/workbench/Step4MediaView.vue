<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { generateAudio, generateVideo } from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  segments: any[];
  frames: any[];
  videos: any[];
  audioTracks: any[];
  tasks: any[];
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();
const videoLoadingId = ref("");
const audioLoadingId = ref("");
const batchVideoRunning = ref(false);
const batchAudioRunning = ref(false);
const batchVideoProgress = ref({ done: 0, total: 0, success: 0, failed: 0 });
const batchAudioProgress = ref({ done: 0, total: 0, success: 0, failed: 0 });
const batchVideoFailures = ref<Array<{ segmentId: string; label: string; message: string }>>([]);
const batchAudioFailures = ref<Array<{ segmentId: string; label: string; message: string }>>([]);
const videoForms = reactive<Record<string, any>>({});
const audioForms = reactive<Record<string, any>>({});

function videoFormOf(segmentId: string) {
  if (!videoForms[segmentId]) {
    videoForms[segmentId] = {
      duration_sec: 3,
      fps: 24,
      width: 1280,
      height: 720,
    };
  }
  return videoForms[segmentId];
}

function audioFormOf(segment: any) {
  if (!audioForms[segment.id]) {
    audioForms[segment.id] = {
      track_type: "NARRATION",
      voice_profile: "",
      text_content: segment.dialogue_text || segment.narration_text || "",
    };
  }
  return audioForms[segment.id];
}

function latestLockedFrame(segmentId: string) {
  return props.frames
    .filter((item) => item.segment_id === segmentId && item.is_locked)
    .sort((a, b) => Number(b.version_no || 0) - Number(a.version_no || 0))[0];
}

function latestVideo(segmentId: string) {
  return props.videos
    .filter((item) => item.segment_id === segmentId)
    .sort((a, b) => Number(b.version_no || 0) - Number(a.version_no || 0))[0];
}

function latestAudio(segmentId: string) {
  return props.audioTracks
    .filter((item) => item.segment_id === segmentId)
    .sort((a, b) => Date.parse(b.updated_at || "") - Date.parse(a.updated_at || ""))[0];
}

function latestFailedTask(segmentId: string, taskType: string) {
  return props.tasks
    .filter(
      (item) =>
        item.entity_type === "segment" &&
        item.entity_id === segmentId &&
        item.task_type === taskType &&
        item.status === "FAILED",
    )
    .sort((a, b) => Date.parse(b.updated_at || b.created_at || "") - Date.parse(a.updated_at || a.created_at || ""))[0];
}

function latestTask(segmentId: string, taskType: string) {
  return props.tasks
    .filter(
      (item) =>
        item.entity_type === "segment" &&
        item.entity_id === segmentId &&
        item.task_type === taskType,
    )
    .sort((a, b) => Date.parse(b.updated_at || b.created_at || "") - Date.parse(a.updated_at || a.created_at || ""))[0];
}

function latestVideoError(segmentId: string) {
  return latestFailedTask(segmentId, "VIDEO_RENDER");
}

function latestAudioError(segmentId: string) {
  return latestFailedTask(segmentId, "TTS_RENDER");
}

function latestVideoTask(segmentId: string) {
  return latestTask(segmentId, "VIDEO_RENDER");
}

function latestAudioTask(segmentId: string) {
  return latestTask(segmentId, "TTS_RENDER");
}

function formatTaskTime(value: string) {
  const time = Date.parse(value || "");
  if (Number.isNaN(time)) return "未知时间";
  return new Date(time).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusLabel(status: string) {
  if (status === "COMPLETED") return "成功";
  if (status === "FAILED") return "失败";
  if (status === "RUNNING") return "运行中";
  return status || "未知";
}

const readyForBatchVideo = computed(() =>
  props.segments.filter((segment) => latestLockedFrame(segment.id)),
);

const readyForBatchAudio = computed(() =>
  props.segments.filter((segment) => {
    const form = audioFormOf(segment);
    const text = form.text_content || segment.dialogue_text || segment.narration_text || segment.visual_desc || "";
    return String(text).trim().length > 0;
  }),
);

async function handleGenerateVideo(segmentId: string) {
  videoLoadingId.value = segmentId;
  try {
    await generateVideo(segmentId, videoFormOf(segmentId));
    toast.success("视频片段已生成");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "生成视频失败"));
  } finally {
    videoLoadingId.value = "";
  }
}

async function handleGenerateAudio(segment: any) {
  audioLoadingId.value = segment.id;
  try {
    await generateAudio(segment.id, audioFormOf(segment));
    toast.success("音频已生成");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "生成音频失败"));
  } finally {
    audioLoadingId.value = "";
  }
}

async function handleBatchGenerateVideo() {
  const targets = readyForBatchVideo.value;
  if (!targets.length) {
    toast.error("当前没有已锁定首帧的分镜可批量生成视频");
    return;
  }

  batchVideoRunning.value = true;
  batchVideoProgress.value = { done: 0, total: targets.length, success: 0, failed: 0 };
  batchVideoFailures.value = [];

  for (const segment of targets) {
    try {
      await generateVideo(segment.id, videoFormOf(segment.id));
      batchVideoProgress.value.success += 1;
    } catch (error) {
      batchVideoProgress.value.failed += 1;
      batchVideoFailures.value.push({
        segmentId: segment.id,
        label: `#${segment.seq_no} ${segment.scene_name || "未命名场景"}`,
        message: getErrorMessage(error, "生成视频失败"),
      });
    } finally {
      batchVideoProgress.value.done += 1;
    }
  }

  batchVideoRunning.value = false;
  toast.success(
    `批量视频生成完成，成功 ${batchVideoProgress.value.success}，失败 ${batchVideoProgress.value.failed}`,
  );
  emit("refresh");
}

async function handleBatchGenerateAudio() {
  const targets = props.segments.filter((segment) => {
    const form = audioFormOf(segment);
    return String(form.text_content || segment.dialogue_text || segment.narration_text || segment.visual_desc || "").trim();
  });
  if (!targets.length) {
    toast.error("当前没有可用于批量生成音频的分镜文本");
    return;
  }

  batchAudioRunning.value = true;
  batchAudioProgress.value = { done: 0, total: targets.length, success: 0, failed: 0 };
  batchAudioFailures.value = [];

  for (const segment of targets) {
    try {
      await generateAudio(segment.id, audioFormOf(segment));
      batchAudioProgress.value.success += 1;
    } catch (error) {
      batchAudioProgress.value.failed += 1;
      batchAudioFailures.value.push({
        segmentId: segment.id,
        label: `#${segment.seq_no} ${segment.scene_name || "未命名场景"}`,
        message: getErrorMessage(error, "生成音频失败"),
      });
    } finally {
      batchAudioProgress.value.done += 1;
    }
  }

  batchAudioRunning.value = false;
  toast.success(
    `批量音频生成完成，成功 ${batchAudioProgress.value.success}，失败 ${batchAudioProgress.value.failed}`,
  );
  emit("refresh");
}
</script>

<template>
  <section class="step-view">
    <h2>Step 4 图生视频与音频</h2>

    <div class="batch-panel">
      <div class="toolbar">
        <button type="button" :disabled="batchVideoRunning || batchAudioRunning || !readyForBatchVideo.length" @click="handleBatchGenerateVideo">
          批量生成全部视频
        </button>
        <button type="button" :disabled="batchAudioRunning || batchVideoRunning || !readyForBatchAudio.length" @click="handleBatchGenerateAudio">
          批量生成全部音频
        </button>
      </div>

      <p v-if="batchVideoRunning" class="batch-progress">
        视频批量进度：{{ batchVideoProgress.done }}/{{ batchVideoProgress.total }}，成功 {{ batchVideoProgress.success }}，失败 {{ batchVideoProgress.failed }}
      </p>
      <p v-if="batchAudioRunning" class="batch-progress">
        音频批量进度：{{ batchAudioProgress.done }}/{{ batchAudioProgress.total }}，成功 {{ batchAudioProgress.success }}，失败 {{ batchAudioProgress.failed }}
      </p>

      <div v-if="batchVideoFailures.length" class="batch-summary-panel">
        <strong>最近一轮视频批量失败</strong>
        <p v-for="item in batchVideoFailures" :key="`${item.segmentId}-video`" class="batch-summary-item">
          {{ item.label }}：{{ item.message }}
        </p>
      </div>

      <div v-if="batchAudioFailures.length" class="batch-summary-panel">
        <strong>最近一轮音频批量失败</strong>
        <p v-for="item in batchAudioFailures" :key="`${item.segmentId}-audio`" class="batch-summary-item">
          {{ item.label }}：{{ item.message }}
        </p>
      </div>
    </div>

    <div class="list-grid" v-if="segments.length">
      <article v-for="segment in segments" :key="segment.id" class="item-card">
        <strong>#{{ segment.seq_no }} {{ segment.scene_name || "未命名场景" }}</strong>
        <p>{{ segment.visual_desc }}</p>
        <p>锁帧：{{ latestLockedFrame(segment.id) ? "已就绪" : "未锁定" }}</p>

        <div class="task-meta-grid">
          <p v-if="latestVideoTask(segment.id)" class="task-meta-item">
            视频任务：{{ statusLabel(latestVideoTask(segment.id).status) }}，{{ formatTaskTime(latestVideoTask(segment.id).updated_at || latestVideoTask(segment.id).created_at) }}
          </p>
          <p v-if="latestAudioTask(segment.id)" class="task-meta-item">
            音频任务：{{ statusLabel(latestAudioTask(segment.id).status) }}，{{ formatTaskTime(latestAudioTask(segment.id).updated_at || latestAudioTask(segment.id).created_at) }}
          </p>
        </div>

        <div v-if="latestVideoError(segment.id)" class="error-panel">
          <strong>最近视频失败</strong>
          <p>{{ latestVideoError(segment.id).error_message || latestVideoError(segment.id).error_code || "未知错误" }}</p>
        </div>

        <div v-if="latestAudioError(segment.id)" class="error-panel">
          <strong>最近音频失败</strong>
          <p>{{ latestAudioError(segment.id).error_message || latestAudioError(segment.id).error_code || "未知错误" }}</p>
        </div>

        <div v-if="latestLockedFrame(segment.id)?.image_url">
          <img :src="`http://127.0.0.1:8000${latestLockedFrame(segment.id).image_url}`" class="preview-image" alt="locked frame" />
        </div>

        <label class="field">
          <span>片段时长（秒）</span>
          <input v-model="videoFormOf(segment.id).duration_sec" type="number" min="1" max="30" />
        </label>

        <label class="field">
          <span>FPS</span>
          <input v-model="videoFormOf(segment.id).fps" type="number" min="1" max="60" />
        </label>

        <div class="toolbar">
          <button
            :disabled="!latestLockedFrame(segment.id) || videoLoadingId === segment.id || batchVideoRunning || batchAudioRunning"
            @click="handleGenerateVideo(segment.id)"
          >
            生成视频片段
          </button>
        </div>

        <video v-if="latestVideo(segment.id)?.video_url" class="preview-media" controls :src="`http://127.0.0.1:8000${latestVideo(segment.id).video_url}`" />
        <p v-if="latestVideo(segment.id)">视频状态：{{ latestVideo(segment.id).status }}，时长 {{ latestVideo(segment.id).duration_sec }}s</p>

        <label class="field">
          <span>TTS 文本</span>
          <textarea v-model="audioFormOf(segment).text_content" class="text-area" rows="4" placeholder="留空则自动使用台词/旁白" />
        </label>

        <label class="field">
          <span>音色</span>
          <input v-model="audioFormOf(segment).voice_profile" placeholder="默认使用后端配置的 TTS_VOICE" />
        </label>

        <div class="toolbar">
          <button :disabled="audioLoadingId === segment.id || batchVideoRunning || batchAudioRunning" @click="handleGenerateAudio(segment)">
            生成音频
          </button>
        </div>

        <audio v-if="latestAudio(segment.id)?.audio_url" class="preview-audio" controls :src="`http://127.0.0.1:8000${latestAudio(segment.id).audio_url}`" />
        <p v-if="latestAudio(segment.id)">音频状态：{{ latestAudio(segment.id).status }}，时长 {{ latestAudio(segment.id).duration_sec || 0 }}s</p>
      </article>
    </div>
  </section>
</template>
