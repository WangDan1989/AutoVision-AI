<script setup lang="ts">
import { reactive, ref } from "vue";

import { rebuildAssets, saveAssetBinding } from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  assets: any[];
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();
const rebuilding = ref(false);
const savingId = ref("");
const forms = reactive<Record<string, any>>({});

function formOf(asset: any) {
  if (!forms[asset.id]) {
    forms[asset.id] = {
      binding_mode: asset.binding?.binding_mode || "LOCAL_LORA",
      lora_enabled: asset.binding?.lora_enabled || false,
      lora_file_path: asset.binding?.lora_file_path || "",
      lora_weight: asset.binding?.lora_weight || 0.75,
      trigger_word: asset.binding?.trigger_word || "",
      ip_adapter_enabled: asset.binding?.ip_adapter_enabled || false,
      ip_adapter_weight: asset.binding?.ip_adapter_weight || 0.6,
      reference_image_paths: asset.binding?.reference_image_paths || [],
      decouple_clothes: asset.binding?.decouple_clothes ?? true,
    };
  }
  return forms[asset.id];
}

async function handleRebuild() {
  rebuilding.value = true;
  try {
    await rebuildAssets(props.projectId);
    toast.success("资产池已重建");
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "重建资产失败"));
  } finally {
    rebuilding.value = false;
  }
}

async function handleSave(asset: any) {
  savingId.value = asset.id;
  try {
    await saveAssetBinding(asset.id, formOf(asset));
    toast.success(`已保存 ${asset.name} 绑定`);
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "保存绑定失败"));
  } finally {
    savingId.value = "";
  }
}
</script>

<template>
  <section class="step-view">
    <div class="toolbar">
      <h2>Step 2 资产绑定</h2>
      <button :disabled="rebuilding" @click="handleRebuild">重建资产池</button>
    </div>

    <div class="list-grid" v-if="assets.length">
      <article v-for="asset in assets" :key="asset.id" class="item-card">
        <strong>{{ asset.name }}</strong>
        <p>类型：{{ asset.asset_type }}</p>

        <label class="field">
          <span>绑定模式</span>
          <select v-model="formOf(asset).binding_mode">
            <option value="LOCAL_LORA">LOCAL_LORA</option>
            <option value="AUTO_TRAIN">AUTO_TRAIN</option>
            <option value="NO_LORA">NO_LORA</option>
          </select>
        </label>

        <label class="field">
          <span>LoRA 文件</span>
          <input v-model="formOf(asset).lora_file_path" placeholder="例如：角色.safetensors" />
        </label>

        <label class="field">
          <span>Trigger Word</span>
          <input v-model="formOf(asset).trigger_word" placeholder="例如：linfeng" />
        </label>

        <label class="field-inline">
          <input type="checkbox" v-model="formOf(asset).lora_enabled" />
          <span>启用 LoRA</span>
        </label>

        <label class="field">
          <span>LoRA 权重</span>
          <input type="number" step="0.05" v-model="formOf(asset).lora_weight" />
        </label>

        <button :disabled="savingId === asset.id" @click="handleSave(asset)">保存绑定</button>
      </article>
    </div>
  </section>
</template>
