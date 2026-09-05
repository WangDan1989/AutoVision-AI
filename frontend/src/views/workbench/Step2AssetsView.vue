<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import {
  rebuildAssets,
  saveAssetBinding,
  saveAssetConsistency,
  uploadMaskFile,
  type ConsistencyConfigTS,
  type SaveConsistencyPayload,
} from "../../api/projectWorkbench";
import { useToastStore } from "../../stores/toast";
import { getErrorMessage } from "../../utils/error";

const props = defineProps<{
  projectId: string;
  assets: any[];
  genreStyle?: string;
}>();

const emit = defineEmits<{
  (e: "refresh"): void;
}>();

const toast = useToastStore();
const rebuilding = ref(false);
const savingId = ref("");
const savingConsistencyId = ref("");
const uploadingRef = reactive<Record<string, boolean>>({});
const consistencyUploadingRef = reactive<Record<string, boolean>>({});
const sceneUploadingRef = reactive<Record<string, boolean>>({});
const previewing = ref<any>(null);
const forms = reactive<Record<string, any>>({});
const innerTabs = reactive<Record<string, string>>({});

const DEFAULT_CONSISTENCY: ConsistencyConfigTS = {
  lockOutfit: false,
  faceTags: [],
  styleLoraName: "",
  styleLoraWeight: 0,
  styleExtraPrompt: "",
  sceneAnchorDesc: "",
  mainCameraTag: "",
  lightingPreset: "",
  lightingColorTempK: 0,
  lightingDirection: "",
  lightingLut: "",
  cameraMovePreset: "",
  camera180Axis: "",
  poseTags: {},
  voicePreset: "",
  voiceEmotionPreset: "",
  consistencyRefImages: [],
  sceneRefImages: [],
};

const GENRE_LABEL_MAP: Record<string, string> = {
  AUTO: "自动识别",
  GUZHUANG_XIANXIA: "古装仙侠",
  GUZHUANG_WUXIA: "古装武侠",
  GUFENG_ZHAIDOU: "古风宅斗",
  XIANDAN_DUSHI: "现代都市",
  XIAOYUAN_QINGCHUN: "校园青春",
  XUANYI_TUILI: "悬疑推理",
  MINGUO_DIEZHAN: "民国谍战",
  KEHUAN_MOSHI: "科幻末世",
  ZHICHANG_JINGYING: "职场经营",
  JIATING_LUNLI: "家庭伦理",
  KAIXIAO_WENNAN: "爆笑微甜",
};

const LIGHTING_PRESETS = [
  { value: "", label: "未设置" },
  { value: "day", label: "☀️ 白天自然阳光" },
  { value: "sunset_golden", label: "🌇 黄金时刻日落" },
  { value: "night", label: "🌙 夜间月光" },
  { value: "indoor_warm", label: "🛋 室内暖光" },
] as const;

const LIGHTING_DIRECTIONS = [
  { value: "", label: "未设置" },
  { value: "top", label: "顶光" },
  { value: "side_left", label: "左侧光" },
  { value: "side_right", label: "右侧光" },
  { value: "back", label: "逆光 / 轮廓光" },
] as const;

const CAMERA_MOVES = [
  { value: "", label: "未设置" },
  { value: "push_in", label: "推镜 (push in)" },
  { value: "pan_left", label: "左摇 (pan left)" },
  { value: "pan_right", label: "右摇 (pan right)" },
  { value: "establishing", label: "建立镜头 (establishing)" },
  { value: "ots", label: "过肩 (over-the-shoulder)" },
] as const;

const LUT_PRESETS = [
  { value: "", label: "未设置" },
  { value: "GUZHUANG_WARM", label: "古装暖金 LUT" },
  { value: "TEAL_ORANGE", label: "青橙电影 LUT" },
  { value: "NOIR_MOODY", label: "悬疑暗调 LUT" },
  { value: "PASTEL_BRIGHT", label: "青春亮彩 LUT" },
] as const;

const ACTIVE_TABS = [
  { value: "CHARACTER", label: "人物 CHARACTER", countOf: (xs: any[]) => xs.filter((x) => x.asset_type === "CHARACTER").length },
  { value: "SCENE", label: "场景 SCENE", countOf: (xs: any[]) => xs.filter((x) => x.asset_type === "SCENE").length },
  { value: "PROP", label: "道具 PROP", countOf: (xs: any[]) => xs.filter((x) => x.asset_type === "PROP").length },
] as const;

const CARD_INNER_TABS = [
  { value: "BIND", label: "🔗 IP-Adapter / LoRA 绑定" },
  { value: "CONSISTENCY", label: "🔒 一致性配置" },
  { value: "LOG", label: "🧾 制作日志" },
] as const;

const activeTab = ref<(typeof ACTIVE_TABS)[number]["value"]>("CHARACTER");

const typeLabelMap: Record<string, string> = {
  CHARACTER: "人物",
  SCENE: "场景",
  PROP: "道具",
};

watch(
  () => props.assets,
  (newAssets) => {
    for (const key of Object.keys(forms)) delete forms[key];
    for (const key of Object.keys(innerTabs)) delete innerTabs[key];
    const wanted = activeTab.value;
    const has = ACTIVE_TABS.some(
      (t) => t.value === wanted && t.countOf(Array.isArray(newAssets) ? newAssets : []) > 0
    );
    if (!has) {
      const firstWithData = ACTIVE_TABS.find((t) => t.countOf(Array.isArray(newAssets) ? newAssets : []) > 0);
      if (firstWithData) activeTab.value = firstWithData.value as any;
    }
  },
  { immediate: true }
);

const filteredAssets = computed(() =>
  props.assets.filter((a) => a.asset_type === activeTab.value)
);

function innerTabOf(asset: any) {
  if (!innerTabs[asset.id]) innerTabs[asset.id] = "BIND";
  return innerTabs[asset.id];
}

function formOf(asset: any) {
  if (!forms[asset.id]) {
    const rawCons = asset.consistency_config || {};
    const snakeToCamel: Record<string, keyof ConsistencyConfigTS> = {
      lock_outfit: "lockOutfit", face_tags: "faceTags", style_lora_name: "styleLoraName",
      style_lora_weight: "styleLoraWeight", style_extra_prompt: "styleExtraPrompt",
      scene_anchor_desc: "sceneAnchorDesc", main_camera_tag: "mainCameraTag",
      lighting_preset: "lightingPreset", lighting_color_temp_k: "lightingColorTempK",
      lighting_direction: "lightingDirection", lighting_lut: "lightingLut",
      camera_move_preset: "cameraMovePreset", camera_180_axis: "camera180Axis",
      pose_tags: "poseTags", voice_preset: "voicePreset",
      voice_emotion_preset: "voiceEmotionPreset",
      consistency_ref_images: "consistencyRefImages", scene_ref_images: "sceneRefImages",
    };
    const normalized: Partial<ConsistencyConfigTS> = {};
    for (const [k, v] of Object.entries(rawCons)) {
      const camelKey = snakeToCamel[k];
      if (camelKey && v !== undefined && v !== null) (normalized as any)[camelKey] = v;
      else if (!(k in snakeToCamel)) (normalized as any)[k] = v;
    }
    const mergedCons: ConsistencyConfigTS = { ...DEFAULT_CONSISTENCY, ...normalized };
    const previewCam: Record<string, string> = {};
    const previewPose: Record<string, string> = {};
    const previewLight: Record<string, string> = {};
    for (const pv of asset.previews || []) {
      previewCam[pv.preview_role] = pv.camera_tag || "";
      const poseFromConfig = mergedCons.poseTags && typeof mergedCons.poseTags === "object"
        ? (mergedCons.poseTags as Record<string, string>)[pv.preview_role] : "";
      previewPose[pv.preview_role] = poseFromConfig || pv.pose_tag || "";
      previewLight[pv.preview_role] = pv.lighting_tag || "";
    }
    forms[asset.id] = {
      binding_mode: asset.binding?.binding_mode || "NO_LORA",
      lora_enabled: asset.binding?.lora_enabled || false,
      lora_file_path: asset.binding?.lora_file_path || "",
      lora_weight: asset.binding?.lora_weight || 0.75,
      trigger_word: asset.binding?.trigger_word || "",
      ip_adapter_enabled: asset.binding?.ip_adapter_enabled || false,
      ip_adapter_weight: asset.binding?.ip_adapter_weight || 0.6,
      reference_image_paths: asset.binding?.reference_image_paths || [],
      decouple_clothes: asset.binding?.decouple_clothes ?? true,
      consistency: mergedCons,
      preview_camera_tags: previewCam,
      preview_pose_tags: previewPose,
      preview_lighting_tags: previewLight,
      face_tags_text: (Array.isArray(mergedCons.faceTags) ? mergedCons.faceTags : []).join(", "),
    };
  }
  return forms[asset.id];
}

function calcConsistencyScore(asset: any): number {
  const f = formOf(asset).consistency as ConsistencyConfigTS;
  let score = 0;
  if (asset.asset_type === "CHARACTER") {
    if (f.lockOutfit || (Array.isArray(f.faceTags) && f.faceTags.length >= 2)) score += 1;
  }
  if (f.styleExtraPrompt || f.styleLoraName) score += 1;
  if (asset.asset_type === "SCENE") {
    if (f.sceneAnchorDesc && f.mainCameraTag) score += 1;
  }
  if (f.cameraMovePreset || f.camera180Axis) score += 1;
  if (f.lightingPreset || (asset.asset_type === "CHARACTER" && f.voicePreset)) score += 1;
  return score;
}

function consistencyBadgeClass(asset: any): string {
  const s = calcConsistencyScore(asset);
  if (s < 2) return "is-low";
  if (s <= 3) return "is-mid";
  return "is-high";
}

function splitFaceTags(asset: any) {
  const text = formOf(asset).face_tags_text || "";
  formOf(asset).consistency.faceTags = text
    .split(/[,，]/)
    .map((s: string) => s.trim())
    .filter(Boolean);
}

async function handleRebuild() {
  rebuilding.value = true;
  try {
    await rebuildAssets(props.projectId);
    const styleName = props.genreStyle
      ? GENRE_LABEL_MAP[props.genreStyle] || props.genreStyle
      : "自动";
    toast.success(
      `资产池已重建（风格=${styleName}），人物/场景/道具多角度预览图生成中…`
    );
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

async function handleSaveConsistency(asset: any) {
  splitFaceTags(asset);
  const f = formOf(asset);
  const c = f.consistency as ConsistencyConfigTS;
  const camelToSnake: Record<keyof ConsistencyConfigTS, string> = {
    lockOutfit: "lock_outfit", faceTags: "face_tags", styleLoraName: "style_lora_name",
    styleLoraWeight: "style_lora_weight", styleExtraPrompt: "style_extra_prompt",
    sceneAnchorDesc: "scene_anchor_desc", mainCameraTag: "main_camera_tag",
    lightingPreset: "lighting_preset", lightingColorTempK: "lighting_color_temp_k",
    lightingDirection: "lighting_direction", lightingLut: "lighting_lut",
    cameraMovePreset: "camera_move_preset", camera180Axis: "camera_180_axis",
    poseTags: "pose_tags", voicePreset: "voice_preset",
    voiceEmotionPreset: "voice_emotion_preset",
    consistencyRefImages: "consistency_ref_images", sceneRefImages: "scene_ref_images",
  };
  const snakeCons: Record<string, any> = {};
  for (const [k, v] of Object.entries(c)) {
    const snakeKey = (camelToSnake as any)[k] || k;
    snakeCons[snakeKey] = v;
  }
  const payload = {
    ...snakeCons,
    preview_camera_tags: f.preview_camera_tags || {},
    preview_pose_tags: f.preview_pose_tags || {},
    preview_lighting_tags: f.preview_lighting_tags || {},
  };
  savingConsistencyId.value = asset.id;
  try {
    await saveAssetConsistency(asset.id, payload as any);
    toast.success(`已保存 ${asset.name} 一致性配置，记得重建资产池才真正生效`);
    emit("refresh");
  } catch (error) {
    toast.error(getErrorMessage(error, "保存一致性配置失败"));
  } finally {
    savingConsistencyId.value = "";
  }
}

function removeRef(asset: any, index: number) {
  formOf(asset).reference_image_paths.splice(index, 1);
}

function removeConsistencyRef(asset: any, index: number) {
  const arr = formOf(asset).consistency.consistencyRefImages;
  if (Array.isArray(arr)) arr.splice(index, 1);
}

function removeSceneRef(asset: any, index: number) {
  const arr = formOf(asset).consistency.sceneRefImages;
  if (Array.isArray(arr)) arr.splice(index, 1);
}

async function uploadRef(asset: any, event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  uploadingRef[asset.id] = true;
  try {
    const r: any = await uploadMaskFile(file);
    const abs = r?.data?.abs_path;
    if (abs) {
      formOf(asset).reference_image_paths.push(abs);
      toast.success("参考图已加入，记得保存绑定");
    } else {
      toast.error("上传返回缺少路径");
    }
  } catch (error) {
    toast.error(getErrorMessage(error, "上传参考图失败"));
  } finally {
    uploadingRef[asset.id] = false;
  }
}

async function uploadConsistencyRef(asset: any, event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  consistencyUploadingRef[asset.id] = true;
  try {
    const r: any = await uploadMaskFile(file);
    const abs = r?.data?.abs_path;
    if (abs) {
      const arr = formOf(asset).consistency.consistencyRefImages;
      if (Array.isArray(arr)) arr.push(abs);
      else formOf(asset).consistency.consistencyRefImages = [abs];
      toast.success("角色三视图/参考图已加入，记得保存一致性配置");
    } else {
      toast.error("上传返回缺少路径");
    }
  } catch (error) {
    toast.error(getErrorMessage(error, "上传参考图失败"));
  } finally {
    consistencyUploadingRef[asset.id] = false;
  }
}

async function uploadSceneRef(asset: any, event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  sceneUploadingRef[asset.id] = true;
  try {
    const r: any = await uploadMaskFile(file);
    const abs = r?.data?.abs_path;
    if (abs) {
      const arr = formOf(asset).consistency.sceneRefImages;
      if (Array.isArray(arr)) arr.push(abs);
      else formOf(asset).consistency.sceneRefImages = [abs];
      toast.success("场景底图已加入，记得保存一致性配置");
    } else {
      toast.error("上传返回缺少路径");
    }
  } catch (error) {
    toast.error(getErrorMessage(error, "上传场景参考图失败"));
  } finally {
    sceneUploadingRef[asset.id] = false;
  }
}

function openPreview(item: any) {
  if (!item?.image_url) return;
  previewing.value = item;
}

function closePreview() {
  previewing.value = null;
}

function standardNegText(asset: any, genreStyle: string | undefined): string {
  const genreCfg = (genreStyle || "AUTO").toUpperCase();
  const genreMap: Record<string, string> = {
    GUZHUANG_XIANXIA: "modern clothes, modern city, cars, technology, english text, photography watermark",
    GUZHUANG_WUXIA: "modern clothes, modern city, guns, neon lights, english text",
    GUFENG_ZHAIDOU: "modern interior, plastic furniture, neon lights, modern clothes",
    XIANDAN_DUSHI: "ancient clothes, traditional hanfu, swords, historical architecture, fantasy creatures",
    XIAOYUAN_QINGCHUN: "adult business suits, old faces, ancient clothes, dark moody scenes",
    XUANYI_TUILI: "bright pastel colors, cartoon, chibi, comedic expression, text watermark",
    MINGUO_DIEZHAN: "modern skyscraper, modern fashion, smartphones, neon, ancient hanfu",
    KEHUAN_MOSHI: "medieval fantasy, horses, swords, ancient architecture, vintage sepia",
    ZHICHANG_JINGYING: "casual street clothes, messy rooms, ancient clothes, fantasy elements",
    JIATING_LUNLI: "office suits, skyscrapers, ancient clothes, fantasy creatures, neon",
    KAIXIAO_WENNAN: "dark moody scenes, horror, violence, blood, noir shadows, crying face",
    AUTO: "",
  };
  const genreNeg = genreMap[genreCfg] || "";
  const baseMap: Record<string, string> = {
    CHARACTER: "landscape, scenery, mountain background, buildings, crowd, multiple people, group photo, environmental shot, out of frame body, face cut off",
    SCENE: "human, person, character, face, portrait, close up of person, figure, animal, giant creature, text overlay, watermark inside scene, close-up cropped detail",
    PROP: "landscape, scenery, mountain, building, architecture, forest environment, human, person, character, face, crowd, animals, background scenery overwhelming",
  };
  const base = baseMap[asset.asset_type] || "";
  const common = "lowres, worst quality, low quality, jpeg artifacts, blurry, out of focus, ugly, deformed, disfigured, bad anatomy, extra limbs, extra digits, extra fingers, watermark, signature, text, logo, border, frame, cropped";
  const parts = [common, base, genreNeg].filter(Boolean);
  return parts.join(", ");
}
</script>

<template>
  <section class="step-view s2-view">
    <div class="toolbar s2-toolbar">
      <div class="s2-toolbar__left">
        <h2>Step 2 资产池</h2>
        <div class="helper-text s2-style-line">
          短剧风格：
          <strong class="s2-style-tag">
            {{ GENRE_LABEL_MAP[genreStyle || "AUTO"] || genreStyle || "自动识别" }}
          </strong>
          <span class="s2-style-hint">
            · 所有人物/场景/道具概念图都会按此风格统一生成，保证风格一致性
          </span>
        </div>
      </div>
      <button class="s2-rebuild-btn" :disabled="rebuilding" @click="handleRebuild">
        {{ rebuilding ? "正在生成多角度预览图…" : "重建资产池" }}
      </button>
    </div>

    <div class="s2-tabs" role="tablist">
      <button
        v-for="tab in ACTIVE_TABS"
        :key="tab.value"
        role="tab"
        class="s2-tab"
        :class="{ 'is-active': activeTab === tab.value }"
        @click="activeTab = tab.value as any"
      >
        <span>{{ tab.label }}</span>
        <span class="s2-tab__count">{{ tab.countOf(assets) }}</span>
      </button>
    </div>

    <div class="s2-empty" v-if="!filteredAssets.length">
      <p>当前分类还没有资产，点击右上角「重建资产池」从剧本自动抽取 人物 / 场景 / 道具。</p>
    </div>

    <div class="list-grid s2-grid" v-else>
      <article v-for="asset in filteredAssets" :key="asset.id" class="item-card s2-card">
        <div class="s2-cover">
          <img v-if="asset.cover_image_url" :src="asset.cover_image_url" :alt="asset.name" />
          <div v-else class="s2-cover__ph">
            <strong>{{ asset.name.slice(0, 1) }}</strong>
            <span>{{ typeLabelMap[asset.asset_type] || asset.asset_type }}</span>
          </div>
          <div class="s2-cover__badge" :class="`is-${asset.status}`">{{ asset.status }}</div>
        </div>

        <div class="s2-title">
          <div class="s2-title__row">
            <strong class="s2-name">{{ asset.name }}</strong>
            <span class="s2-consistency-badge" :class="consistencyBadgeClass(asset)">
              一致性 {{ calcConsistencyScore(asset) }}/5
            </span>
          </div>
          <p class="s2-meta">
            <span class="s2-type-tag">{{ typeLabelMap[asset.asset_type] || asset.asset_type }}</span>
            <span class="s2-canonical" v-if="asset.canonical_name && asset.canonical_name !== asset.name">
              规范名：{{ asset.canonical_name }}
            </span>
          </p>
          <p v-if="asset.description" class="s2-desc">{{ asset.description }}</p>
        </div>

        <div class="s2-previews">
          <div class="s2-previews__header">
            <strong>多角度预览</strong>
            <span class="helper-text">
              保证人物一致性 / 场景切换流畅度 · 点图放大查看
            </span>
          </div>
          <div class="s2-previews__grid">
            <div
              v-for="(pv, idx) in (asset.previews || [])"
              :key="pv.id || idx"
              class="s2-pv"
              :class="{ 'is-loading': pv.status === 'PENDING' }"
            >
              <div class="s2-pv__img" @click="openPreview(pv)">
                <img v-if="pv.image_url" :src="pv.image_url" :alt="pv.preview_label || asset.name" loading="lazy" />
                <div v-else class="s2-pv__ph">
                  <strong>{{ pv.status === "PENDING" ? "…" : pv.status === "FAILED" ? "!" : asset.name.slice(0, 1) }}</strong>
                  <span>{{ pv.preview_label || "预览" }}</span>
                </div>
                <div class="s2-pv__badge" :class="`is-${pv.status}`">{{ pv.status }}</div>
              </div>
              <div class="s2-pv__label">
                <span>{{ pv.preview_label || pv.preview_role }}</span>
                <span class="helper-text" v-if="pv.width && pv.height">{{ pv.width }}×{{ pv.height }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="s2-card-inner-tabs">
          <button
            v-for="t in CARD_INNER_TABS"
            :key="t.value"
            class="s2-inner-tab"
            :class="{ 'is-active': innerTabOf(asset) === t.value }"
            @click="innerTabs[asset.id] = t.value"
          >
            <span>{{ t.label }}</span>
          </button>
        </div>

        <div v-show="innerTabOf(asset) === 'BIND'">
          <label class="field">
            <span>绑定模式</span>
            <select v-model="formOf(asset).binding_mode">
              <option value="LOCAL_LORA">LOCAL_LORA</option>
              <option value="AUTO_TRAIN">AUTO_TRAIN</option>
              <option value="NO_LORA">NO_LORA</option>
            </select>
          </label>

          <div class="s2-row-2">
            <label class="field">
              <span>LoRA 文件</span>
              <input v-model="formOf(asset).lora_file_path" placeholder="例如：角色.safetensors" />
            </label>
            <label class="field">
              <span>Trigger Word</span>
              <input v-model="formOf(asset).trigger_word" placeholder="例如：linfeng" />
            </label>
          </div>

          <div class="s2-row-3">
            <label class="field-inline">
              <input type="checkbox" v-model="formOf(asset).lora_enabled" />
              <span>启用 LoRA</span>
            </label>
            <label class="field field--inline">
              <span>LoRA 权重</span>
              <input type="number" step="0.05" v-model="formOf(asset).lora_weight" />
            </label>
            <label class="field field--inline">
              <span>IP-Adapter 权重</span>
              <input type="number" step="0.05" v-model="formOf(asset).ip_adapter_weight" />
            </label>
          </div>

          <div class="s2-refs">
            <div class="s2-previews__header">
              <strong>参考图（IP-Adapter 一致性绑定）</strong>
            </div>
            <div class="s2-ref-grid">
              <div
                v-for="(p, i) in (asset.binding?.reference_image_urls || [])"
                :key="i"
                class="s2-ref-item"
              >
                <img v-if="p" :src="p" @click="openPreview({ image_url: p, preview_label: `参考图${i + 1}` })" />
                <button class="s2-ref-remove" @click="removeRef(asset, i)">×</button>
              </div>
              <label class="s2-ref-upload" :class="{ 'is-loading': uploadingRef[asset.id] }">
                <input
                  type="file"
                  accept="image/*"
                  :disabled="uploadingRef[asset.id]"
                  @change="uploadRef(asset, $event)"
                  hidden
                />
                <span>{{ uploadingRef[asset.id] ? "上传中…" : "+ 上传" }}</span>
              </label>
            </div>
            <p class="helper-text s2-ref-hint">
              上传后路径会写入当前绑定表单，记得点「保存绑定」才真正落库。
            </p>
          </div>

          <button class="s2-save-btn" :disabled="savingId === asset.id" @click="handleSave(asset)">
            {{ savingId === asset.id ? "保存中…" : "保存绑定" }}
          </button>
        </div>

        <div v-show="innerTabOf(asset) === 'CONSISTENCY'">
          <div v-if="asset.asset_type === 'CHARACTER'" class="s2-collapse">
            <div class="s2-collapse__header">
              <strong>👤 角色形象一致性</strong>
            </div>
            <div class="s2-collapse__body">
              <div class="s2-previews__header" style="margin: 0 0 8px">
                <strong>定妆三视图 Turnaround Sheet</strong>
                <span class="helper-text">蓝色徽章的角度对应定妆视角</span>
              </div>
              <div class="s2-previews__grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 12px">
                <div class="s2-pv" v-for="pv in (asset.previews || []).filter(p => p.preview_role === 'FRONT_FULL' || p.preview_role === 'SIDE_HALF' || p.preview_role === 'BACK_FULL')" :key="pv.preview_role">
                  <div class="s2-pv__img" @click="openPreview(pv)">
                    <img v-if="pv.image_url" :src="pv.image_url" :alt="pv.preview_label" loading="lazy" />
                    <div v-else class="s2-pv__ph"><span>{{ pv.preview_label || pv.preview_role }}</span></div>
                    <div class="s2-pv__badge" style="background: rgba(56,128,255,0.92)">
                      TURN_{{ pv.preview_role }}
                    </div>
                  </div>
                </div>
              </div>

              <label class="field" style="margin-bottom: 10px">
                <span>显著特征记忆点（用英文逗号分隔，AI 最高权重前缀）</span>
                <input
                  v-model="formOf(asset).face_tags_text"
                  placeholder="例如：blue teardrop mole below left eye, black jade hairpin, white silk waistband"
                />
              </label>

              <label class="field-inline" style="margin-bottom: 12px">
                <input type="checkbox" v-model="formOf(asset).consistency.lockOutfit" />
                <span style="font-weight: 600">🔒 常服锁死（除非剧情变装，否则禁止换衣/配饰渐变）</span>
              </label>

              <div class="s2-previews__header" style="margin: 0 0 8px">
                <strong>角色参考图（FaceID / IP-Adapter 锚点）</strong>
                <span class="helper-text">3 张不同角度定妆照</span>
              </div>
              <div class="s2-ref-grid">
                <div
                  v-for="(p, i) in (formOf(asset).consistency.consistencyRefImages || [])"
                  :key="'cref'+i"
                  class="s2-ref-item"
                >
                  <img v-if="p" :src="p" @click="openPreview({ image_url: p, preview_label: `角色锚点${i + 1}` })" />
                  <button class="s2-ref-remove" @click="removeConsistencyRef(asset, i)">×</button>
                </div>
                <label class="s2-ref-upload" v-if="(formOf(asset).consistency.consistencyRefImages || []).length < 3"
                  :class="{ 'is-loading': consistencyUploadingRef[asset.id] }">
                  <input type="file" accept="image/*" :disabled="consistencyUploadingRef[asset.id]"
                    @change="uploadConsistencyRef(asset, $event)" hidden />
                  <span>{{ consistencyUploadingRef[asset.id] ? "上传中…" : "+ 上传锚点" }}</span>
                </label>
              </div>
            </div>
          </div>

          <div class="s2-collapse">
            <div class="s2-collapse__header">
              <strong>🎨 视觉画风一致性</strong>
            </div>
            <div class="s2-collapse__body">
              <label class="field" style="margin-bottom: 10px">
                <span>底模 Base Model（全剧统一，只读）</span>
                <input value="v1-5-pruned-emaonly.safetensors （全剧统一，请勿混用）" readonly />
                <span class="helper-text" style="color: #d9a33a; font-weight:600">⚠️ 请勿混用不同底模，避免风格跳变</span>
              </label>

              <div class="s2-row-2" style="margin-bottom: 10px">
                <label class="field">
                  <span>Style LoRA 名称（可留空）</span>
                  <input v-model="formOf(asset).consistency.styleLoraName" placeholder="例如：guofeng_ink_v2.safetensors" />
                </label>
                <label class="field">
                  <span>LoRA 权重（0-2）</span>
                  <input type="number" step="0.05" min="0" max="2" v-model="formOf(asset).consistency.styleLoraWeight" />
                </label>
              </div>

              <label class="field" style="margin-bottom: 10px">
                <span>风格附加提示词（强制注入 Prompt 中段）</span>
                <textarea rows="2" v-model="formOf(asset).consistency.styleExtraPrompt"
                  placeholder="例如：ink painting palette, studio ghibli aesthetic, clean line art, cel shading"></textarea>
              </label>

              <div>
                <span class="s2-previews__header" style="margin:0 0 6px; display:flex"><strong>规范化负向提示词 Negative Prompt（只读）</strong></span>
                <pre class="s2-log-panel" style="max-height: 110px; overflow:auto; margin:0; color:#c9cbd9">{{ standardNegText(asset, genreStyle) }}</pre>
              </div>
            </div>
          </div>

          <div v-if="asset.asset_type === 'SCENE'" class="s2-collapse">
            <div class="s2-collapse__header">
              <strong>🏞 场景与空间一致性</strong>
            </div>
            <div class="s2-collapse__body">
              <label class="field" style="margin-bottom: 10px">
                <span>主相机机位标签（写入每张镜头 Prompt）</span>
                <input v-model="formOf(asset).consistency.mainCameraTag" placeholder="例如：eye level trail cam, 24mm wide lens" />
              </label>

              <label class="field" style="margin-bottom: 10px">
                <span>空间锚点描述（固定建筑 / 家具 / 路径结构）</span>
                <textarea rows="3" v-model="formOf(asset).consistency.sceneAnchorDesc"
                  placeholder="例如：bluestone steps winding through pine forest, left side handrail rope, distant mountain silhouette"></textarea>
              </label>

              <div class="s2-previews__header" style="margin: 0 0 8px">
                <strong>场景底图垫图（Img2Img / 背景替换用）</strong>
                <span class="helper-text">2 张不同视角高清底图</span>
              </div>
              <div class="s2-ref-grid">
                <div
                  v-for="(p, i) in (formOf(asset).consistency.sceneRefImages || [])"
                  :key="'sref'+i"
                  class="s2-ref-item"
                >
                  <img v-if="p" :src="p" @click="openPreview({ image_url: p, preview_label: `场景底图${i + 1}` })" />
                  <button class="s2-ref-remove" @click="removeSceneRef(asset, i)">×</button>
                </div>
                <label class="s2-ref-upload" v-if="(formOf(asset).consistency.sceneRefImages || []).length < 2"
                  :class="{ 'is-loading': sceneUploadingRef[asset.id] }">
                  <input type="file" accept="image/*" :disabled="sceneUploadingRef[asset.id]"
                    @change="uploadSceneRef(asset, $event)" hidden />
                  <span>{{ sceneUploadingRef[asset.id] ? "上传中…" : "+ 上传底图" }}</span>
                </label>
              </div>
            </div>
          </div>

          <div v-if="asset.asset_type === 'CHARACTER' || asset.asset_type === 'SCENE'" class="s2-collapse">
            <div class="s2-collapse__header">
              <strong>🎬 镜头语言与动作连贯性</strong>
            </div>
            <div class="s2-collapse__body">
              <div v-if="asset.asset_type === 'CHARACTER'" style="margin-bottom: 12px">
                <span class="s2-previews__header" style="display:flex; margin:0 0 6px"><strong>单镜头动作 / 姿态 Tag（每张预览可编辑）</strong></span>
                <div class="s2-row-2" style="margin-bottom:4px" v-for="pv in (asset.previews || [])" :key="'pose'+pv.id">
                  <label class="field" style="grid-column: span 2">
                    <span>{{ pv.preview_label || pv.preview_role }} · pose_tag</span>
                    <input v-model="formOf(asset).preview_pose_tags[pv.preview_role]"
                      placeholder="例如：standing relaxed with both hands by sides, looking at viewer" />
                  </label>
                </div>
              </div>

              <label class="field" style="margin-bottom: 10px">
                <span>运镜预设 Camera Move（每张镜头追加）</span>
                <select v-model="formOf(asset).consistency.cameraMovePreset">
                  <option v-for="c in CAMERA_MOVES" :key="c.value" :value="c.value">{{ c.label }}</option>
                </select>
              </label>

              <label class="field-inline" style="margin-bottom: 4px">
                <span style="font-weight:600; width: 150px">180° 轴线方向：</span>
              </label>
              <div style="display:flex; gap:16px; padding: 6px 4px 12px">
                <label class="field-inline">
                  <input type="radio" :name="'axis_'+asset.id" value="left"
                    v-model="formOf(asset).consistency.camera180Axis" />
                  <span>← 角色朝左（轴线左侧）</span>
                </label>
                <label class="field-inline">
                  <input type="radio" :name="'axis_'+asset.id" value="right"
                    v-model="formOf(asset).consistency.camera180Axis" />
                  <span>角色朝右 →（轴线右侧）</span>
                </label>
              </div>
            </div>
          </div>

          <div class="s2-collapse">
            <div class="s2-collapse__header">
              <strong>💡 影调布光与后期一致性</strong>
            </div>
            <div class="s2-collapse__body">
              <div class="s2-row-2" style="margin-bottom: 10px">
                <label class="field">
                  <span>主光源类型 Lighting Preset</span>
                  <select v-model="formOf(asset).consistency.lightingPreset">
                    <option v-for="l in LIGHTING_PRESETS" :key="l.value" :value="l.value">{{ l.label }}</option>
                  </select>
                </label>
                <label class="field">
                  <span>色温 K（1000-10000）</span>
                  <input type="number" step="100" min="1000" max="10000" v-model="formOf(asset).consistency.lightingColorTempK" />
                </label>
              </div>

              <label class="field-inline" style="margin-bottom: 10px">
                <span style="font-weight:600; width: 120px">主光源方向：</span>
              </label>
              <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px; padding: 0 4px 10px">
                <label class="field-inline" v-for="d in LIGHTING_DIRECTIONS" :key="d.value">
                  <input type="radio" :name="'light_'+asset.id" :value="d.value"
                    v-model="formOf(asset).consistency.lightingDirection" />
                  <span>{{ d.label }}</span>
                </label>
              </div>

              <label class="field" style="margin-bottom: 10px">
                <span>统一调色 LUT（后期套色）</span>
                <select v-model="formOf(asset).consistency.lightingLut">
                  <option v-for="l in LUT_PRESETS" :key="l.value" :value="l.value">{{ l.label }}</option>
                </select>
              </label>

              <div v-if="asset.asset_type === 'CHARACTER'" style="padding-top: 8px; border-top:1px dashed rgba(255,255,255,0.08)">
                <strong style="color:#8f84ff">🎙 配音音色一致性（TTS / 声音克隆）</strong>
                <div class="s2-row-2" style="margin-top: 8px">
                  <label class="field" style="grid-column: span 2">
                    <span>音色预设名称（edge-tts / 克隆音色）</span>
                    <input v-model="formOf(asset).consistency.voicePreset" placeholder="例如：zh-CN-YunxiNeural / xiaoxiao_clone_v3" />
                  </label>
                  <label class="field" style="grid-column: span 2">
                    <span>情绪音色库（逗号分隔，按场景切换）</span>
                    <input v-model="formOf(asset).consistency.voiceEmotionPreset" placeholder="例如：calm, angry_whisper, gentle_smile, urgent" />
                  </label>
                </div>
              </div>
            </div>
          </div>

          <button class="s2-save-consistency-btn" :disabled="savingConsistencyId === asset.id"
            @click="handleSaveConsistency(asset)">
            {{ savingConsistencyId === asset.id ? "💾 正在保存一致性配置…" : "💾 保存一致性配置（需重建资产池生效）" }}
          </button>
        </div>

        <div v-show="innerTabOf(asset) === 'LOG'">
          <div class="s2-log-panel" style="padding: 12px 14px">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
              <strong style="font-size:14px">🧾 制作日志 Production Log</strong>
              <span class="s2-consistency-badge" :class="consistencyBadgeClass(asset)"
                style="font-size:13px; padding:5px 14px">一致性 {{ calcConsistencyScore(asset) }}/5</span>
            </div>
            <div style="display:grid; grid-template-columns: repeat(5,1fr); gap:8px; margin-bottom:12px; font-size:12px">
              <div class="s2-collapse" style="padding: 8px 10px">
                <span style="color:var(--text-muted)">Sampler</span>
                <div style="font-weight:600">{{ asset.production_log?.sampler || 'euler' }}</div>
              </div>
              <div class="s2-collapse" style="padding: 8px 10px">
                <span style="color:var(--text-muted)">Steps</span>
                <div style="font-weight:600">{{ asset.production_log?.steps || 24 }}</div>
              </div>
              <div class="s2-collapse" style="padding: 8px 10px">
                <span style="color:var(--text-muted)">CFG Scale</span>
                <div style="font-weight:600">{{ asset.production_log?.cfg || 7 }}</div>
              </div>
              <div class="s2-collapse" style="padding: 8px 10px">
                <span style="color:var(--text-muted)">Checkpoint</span>
                <div style="font-weight:600; font-size:11px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap"
                  :title="asset.production_log?.checkpoint">{{ (asset.production_log?.checkpoint || 'v1-5-pruned').slice(0,18) }}…</div>
              </div>
              <div class="s2-collapse" style="padding: 8px 10px">
                <span style="color:var(--text-muted)">Seed Hash</span>
                <div style="font-weight:600; font-family:monospace">{{ asset.production_log?.seed_hash_prefix || '--------' }}</div>
              </div>
            </div>
            <div style="margin-bottom: 10px">
              <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px">封面 Prompt：</div>
              <pre style="margin:0; white-space:pre-wrap; word-break:break-all; font-size:11.5px; color:#dfe1ee; background:rgba(0,0,0,0.25); padding:8px 10px; border-radius:6px">{{ asset.cover_prompt_text || '（封面待重建）' }}</pre>
            </div>
            <div v-if="(asset.previews||[]).length">
              <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px">第一张预览 Prompt（{{ asset.previews[0].preview_label || asset.previews[0].preview_role }}）：</div>
              <pre style="margin:0; white-space:pre-wrap; word-break:break-all; font-size:11.5px; color:#dfe1ee; background:rgba(0,0,0,0.25); padding:8px 10px; border-radius:6px; max-height:160px; overflow:auto">{{ asset.previews[0].prompt_text || '（预览待重建）' }}</pre>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="previewing" class="s2-modal-mask" @click.self="closePreview">
      <div class="s2-modal">
        <header class="s2-modal__header">
          <strong>{{ previewing.preview_label || "预览" }}</strong>
          <button class="ghost-btn" @click="closePreview">关闭</button>
        </header>
        <div class="s2-modal__body">
          <img v-if="previewing.image_url" :src="previewing.image_url" :alt="previewing.preview_label" />
        </div>
        <footer class="s2-modal__footer helper-text" v-if="previewing.prompt_text">
          Prompt：{{ previewing.prompt_text }}
        </footer>
      </div>
    </div>
  </section>
</template>

<style scoped>
.s2-view { padding-top: 8px; }

.s2-toolbar {
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
}
.s2-toolbar__left { display: flex; flex-direction: column; gap: 6px; }
.s2-toolbar__left h2 { margin: 0; }
.s2-style-line { margin: 0; font-size: 13px; }
.s2-style-tag {
  display: inline-block;
  margin: 0 4px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(76, 60, 255, 0.12);
  color: #4c3cff;
  font-weight: 600;
}
.s2-style-hint { opacity: 0.75; }
.s2-rebuild-btn {
  background: #4c3cff;
  color: #fff;
  border-color: #4c3cff;
  font-weight: 600;
  padding: 10px 16px;
  border-radius: 10px;
}
.s2-rebuild-btn:disabled { opacity: 0.65; cursor: wait; }

.s2-tabs {
  display: flex;
  gap: 8px;
  padding: 4px;
  margin: 12px 0 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.s2-tab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s;
}
.s2-tab:hover { color: #fff; background: rgba(255,255,255,0.05); }
.s2-tab.is-active {
  background: #4c3cff;
  border-color: #4c3cff;
  color: #fff;
}
.s2-tab__count {
  min-width: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: inherit;
  font-size: 12px;
  line-height: 18px;
  text-align: center;
}
.s2-tab.is-active .s2-tab__count { background: rgba(255,255,255,0.22); }

.s2-empty {
  padding: 36px 20px;
  text-align: center;
  color: var(--text-muted);
  border: 1px dashed rgba(255, 255, 255, 0.16);
  border-radius: 12px;
}

.s2-grid { --gap: 18px; }

.s2-card { padding: 16px; }

.s2-cover { margin-bottom: 10px; }

.s2-title { margin-bottom: 10px; }
.s2-title strong { font-size: 16px; }
.s2-meta { margin: 4px 0 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.s2-type-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(76,60,255,0.12);
  color: #8f84ff;
  font-weight: 600;
}
.s2-canonical { color: var(--text-muted); font-size: 12px; }
.s2-desc {
  margin: 6px 0 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255,255,255,0.06);
  font-size: 12px;
  color: #c9cbd9;
  line-height: 1.55;
}

.s2-previews {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255,255,255,0.06);
}
.s2-previews__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}
.s2-previews__header strong { color: #fff; }

.s2-previews__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.s2-pv { display: flex; flex-direction: column; gap: 4px; }
.s2-pv.is-loading { opacity: 0.75; }
.s2-pv__img {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #181a20;
  border: 1px solid rgba(255,255,255,0.06);
  cursor: zoom-in;
}
.s2-pv__img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.s2-pv__ph {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.72);
  background: linear-gradient(135deg, #232632, #15171c);
}
.s2-pv__ph strong { font-size: 28px; color: #fff; opacity: 0.9; }
.s2-pv__ph span {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
}
.s2-pv__badge {
  position: absolute;
  top: 4px;
  right: 4px;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 10px;
  background: rgba(0,0,0,0.6);
  color: #fff;
}
.s2-pv__badge.is-COMPLETED { background: rgba(32, 170, 94, 0.9); }
.s2-pv__badge.is-PENDING { background: rgba(240, 150, 30, 0.9); }
.s2-pv__badge.is-FAILED { background: rgba(210, 55, 70, 0.95); }
.s2-pv__label {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  font-size: 12px;
  color: #dfe1ee;
}

.s2-row-2, .s2-row-3 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 4px;
}
.s2-row-3 { grid-template-columns: auto 1fr 1fr; align-items: center; }
.field--inline { display: grid; grid-template-columns: 1fr; }
.field--inline > span { margin-bottom: 4px; }

.s2-refs { margin: 8px 0 12px; }

.s2-save-btn {
  background: #4c3cff;
  color: #fff;
  border-color: #4c3cff;
  font-weight: 600;
  padding: 10px 14px;
  border-radius: 10px;
  width: 100%;
}
.s2-save-btn:disabled { opacity: 0.65; cursor: wait; }

.s2-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  padding: 20px;
}
.s2-modal {
  width: min(1024px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  background: #1e2028;
  border: 1px solid rgba(255,255,255,0.1);
  overflow: hidden;
}
.s2-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.s2-modal__body {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background: #0e0f14;
}
.s2-modal__body img {
  width: 100%;
  height: auto;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 10px;
}
.s2-modal__footer {
  padding: 10px 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
  line-height: 1.6;
  word-break: break-all;
}

@media (min-width: 900px) {
  .s2-previews__grid { grid-template-columns: repeat(3, 1fr); }
}

.s2-title__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.s2-consistency-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
.s2-consistency-badge.is-low { background: #dc3b48; color: #fff; }
.s2-consistency-badge.is-mid { background: #d9a33a; color: #17181d; }
.s2-consistency-badge.is-high { background: #29a15f; color: #fff; }

.s2-card-inner-tabs {
  display: flex;
  gap: 6px;
  padding: 4px;
  margin: 4px 0 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255,255,255,0.07);
}
.s2-inner-tab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 500;
  transition: all 0.15s;
}
.s2-inner-tab:hover { color: #fff; background: rgba(255,255,255,0.045); }
.s2-inner-tab.is-active {
  background: #4c3cff;
  border-color: #4c3cff;
  color: #fff;
  font-weight: 600;
}

.s2-collapse {
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  margin-bottom: 10px;
  background: rgba(255, 255, 255, 0.025);
  overflow: hidden;
}
.s2-collapse__header {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.s2-collapse__header strong { font-size: 13.5px; }
.s2-collapse__body { padding: 10px 12px 12px; }

.s2-save-consistency-btn {
  width: 100%;
  background: #8f4cff;
  color: #fff;
  border: 1px solid #8f4cff;
  font-weight: 600;
  padding: 11px 14px;
  border-radius: 10px;
  margin-top: 6px;
  font-size: 14px;
}
.s2-save-consistency-btn:disabled { opacity: 0.65; cursor: wait; }
.s2-save-consistency-btn:hover:not(:disabled) {
  background: #7a33ff;
  border-color: #7a33ff;
}

.s2-log-panel {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  color: #dfe1ee;
}
</style>
