<script setup lang="ts">
import { ref } from "vue";

import { parseScript } from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  segments: any[];
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();
const rawScriptText = ref("");
const submitting = ref(false);

async function handleParse() {
  if (!rawScriptText.value.trim()) {
    toast.error("请先输入剧本文本");
    return;
  }
  submitting.value = true;
  try {
    await parseScript(props.projectId, rawScriptText.value);
    toast.success("剧本拆解完成");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "剧本拆解失败"));
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="step-view">
    <h2>Step 1 剧本拆解</h2>

    <textarea
      v-model="rawScriptText"
      class="text-area"
      rows="10"
      placeholder="在这里粘贴完整小说或剧本文本"
    />

    <div class="toolbar">
      <button :disabled="submitting" @click="handleParse">开始拆解</button>
    </div>

    <div class="list-grid" v-if="segments.length">
      <article v-for="segment in segments" :key="segment.id" class="item-card">
        <strong>#{{ segment.seq_no }} {{ segment.scene_name || "未命名场景" }}</strong>
        <p>{{ segment.visual_desc }}</p>
        <p>镜头：{{ segment.camera_lang || "未填写" }}</p>
        <p>角色：{{ (segment.character_ids || []).join("、") || "无" }}</p>
        <p v-if="segment.dialogue_text">台词：{{ segment.dialogue_text }}</p>
      </article>
    </div>
  </section>
</template>
