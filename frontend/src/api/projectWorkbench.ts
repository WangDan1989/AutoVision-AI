import { api } from "../utils/api";

export interface ConsistencyConfigTS {
  lock_outfit: boolean;
  face_tags: string[];
  style_lora_name: string;
  style_lora_weight: number;
  style_extra_prompt: string;
  scene_anchor_desc: string;
  main_camera_tag: string;
  lighting_preset: string;
  lighting_color_temp_k: number;
  lighting_direction: string;
  lighting_lut: string;
  camera_move_preset: string;
  camera_180_axis: "left" | "right" | "";
  pose_tags: Record<string, string>;
  voice_preset: string;
  voice_emotion_preset: string;
  consistency_ref_images: string[];
  scene_ref_images: string[];
}

export type SaveConsistencyPayload = ConsistencyConfigTS & {
  preview_camera_tags: Record<string, string>;
  preview_pose_tags: Record<string, string>;
  preview_lighting_tags: Record<string, string>;
};

export function getProjects() {
  return api.get("/api/projects");
}

export function createProject(payload: any) {
  return api.post("/api/projects", payload);
}

export function getProject(projectId: string) {
  return api.get(`/api/projects/${projectId}`);
}

export function deleteProject(projectId: string) {
  return api.delete(`/api/projects/${projectId}`, { data: { confirm: true } });
}

export function updateProjectPreferences(projectId: string, preferences: any) {
  return api.patch(`/api/projects/${projectId}/preferences`, preferences);
}

export function getTasks(projectId?: string) {
  return api.get("/api/tasks", { params: { project_id: projectId } });
}

export function parseScript(projectId: string, rawScriptText: string) {
  return api.post(`/api/projects/${projectId}/script/parse`, {
    raw_script_text: rawScriptText,
  });
}

export function getSegments(projectId: string) {
  return api.get(`/api/projects/${projectId}/segments`);
}

export function rebuildAssets(projectId: string) {
  return api.post(`/api/projects/${projectId}/assets/rebuild`);
}

export function getAssets(projectId: string) {
  return api.get(`/api/projects/${projectId}/assets`);
}

export function saveAssetBinding(assetId: string, payload: any) {
  return api.post(`/api/assets/${assetId}/bindings`, payload);
}

export function saveAssetConsistency(assetId: string, payload: SaveConsistencyPayload) {
  return api.post(`/api/assets/${assetId}/consistency`, payload);
}

export function generateFrame(segmentId: string, payload: any) {
  return api.post(`/api/segments/${segmentId}/frames/generate`, payload);
}

export function lockFrame(frameId: string, isLocked: boolean) {
  return api.post(`/api/frames/${frameId}/lock`, { is_locked: isLocked });
}

export function getFrames(projectId: string) {
  return api.get(`/api/projects/${projectId}/frames`);
}

export function generateVideo(segmentId: string, payload: any) {
  return api.post(`/api/segments/${segmentId}/videos/generate`, payload);
}

export function getVideos(projectId: string) {
  return api.get(`/api/projects/${projectId}/videos`);
}

export function generateAudio(segmentId: string, payload: any) {
  return api.post(`/api/segments/${segmentId}/audio/generate`, payload);
}

export function getAudioTracks(projectId: string) {
  return api.get(`/api/projects/${projectId}/audio`);
}

export function generateExport(projectId: string, payload: any) {
  return api.post(`/api/projects/${projectId}/exports/generate`, payload);
}

export function getExports(projectId: string) {
  return api.get(`/api/projects/${projectId}/exports`);
}

export function uploadMaskFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/api/uploads/mask", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
