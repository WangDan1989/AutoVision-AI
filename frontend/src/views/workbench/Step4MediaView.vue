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

  for (const segment of targets) {
    try {
      await generateVideo(segment.id, videoFormOf(segment.id));
      batchVideoProgress.value.success += 1;
    } catch {
      batchVideoProgress.value.failed += 1;
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

  for (const segment of targets) {
    try {
      await generateAudio(segment.id, audioFormOf(segment));
      batchAudioProgress.value.success += 1;
    } catch {
      batchAudioProgress.value.failed += 1;
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
    </div>

    <div class="list-grid" v-if="segments.length">
      <article v-for="segment in segments" :key="segment.id" class="item-card">
        <strong>#{{ segment.seq_no }} {{ segment.scene_name || "未命名场景" }}</strong>
        <p>{{ segment.visual_desc }}</p>
        <p>锁帧：{{ latestLockedFrame(segment.id) ? "已就绪" : "未锁定" }}</p>

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
