import { api } from "../utils/api";

export function getProjects() {
  return api.get("/api/projects");
}

export function getProject(projectId: string) {
  return api.get(`/api/projects/${projectId}`);
}

export function getTasks(projectId?: string) {
  return api.get("/api/tasks", { params: { project_id: projectId } });
}

export function uploadMaskFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/api/uploads/mask", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
