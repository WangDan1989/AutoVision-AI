import { api } from "../utils/api";

export function getProjects() {
  return api.get("/api/projects");
}

export function getProject(projectId: string) {
  return api.get(`/api/projects/${projectId}`);
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
