import type {
  Character,
  ClipEdit,
  ContentBrief,
  GenerateOptions,
  Project,
  ProjectInput,
  ProjectListItem,
  PublicationFeedback,
  ReviewStage,
  Script,
  Settings,
  SettingsInput,
  ShotInput,
  StylePreset,
  WorkbenchStatus,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}
// All writes retain the workbench marker; paid POSTs are never retried.
export async function request<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { "X-Drama-Client": "1" };
  const form = data instanceof FormData;
  if (data !== undefined && !form) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: form ? data : data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      typeof result?.detail === "string"
        ? result.detail
        : "请求失败，请检查本地服务",
      response.status,
    );
  return result as T;
}
export const api = {
  status: () => request<WorkbenchStatus>("/api/status"),
  settings: (data: SettingsInput) =>
    request<Settings>("/api/settings", "PUT", data),
  stylePresets: () => request<StylePreset[]>("/api/style-presets"),
  saveStylePreset: (data: { name: string; style: string }) =>
    request<StylePreset>("/api/style-presets", "POST", data),
  recommendStyle: (id: string) =>
    request<Project>(`/api/projects/${id}/style/recommend`, "POST", {}),
  acceptStyle: (id: string) =>
    request<Project>(`/api/projects/${id}/style/accept`, "POST", {}),
  projects: () => request<ProjectListItem[]>("/api/projects"),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (data: ProjectInput) =>
    request<Project>("/api/projects", "POST", data),
  updateProject: (id: string, data: ProjectInput) =>
    request<Project>(`/api/projects/${id}`, "PUT", data),
  plan: (id: string) =>
    request<Project>(`/api/projects/${id}/plan`, "POST", { mode: "ai" }),
  importScript: (id: string, data: Script) =>
    request<Project>(`/api/projects/${id}/scripts`, "POST", data),
  selectScript: (id: string, sid: string) =>
    request<Project>(`/api/projects/${id}/scripts/${sid}/select`, "POST", {}),
  approve: (id: string, stage: "script" | "characters" | "shots") =>
    request<Project>(`/api/projects/${id}/approve/${stage}`, "POST", {}),
  brief: (id: string, data: ContentBrief) =>
    request<Project>(`/api/projects/${id}/brief`, "PUT", data),
  draftBrief: (id: string) =>
    request<Project>(`/api/projects/${id}/brief/draft`, "POST", {}),
  reviewWorkflow: (
    id: string,
    stage: ReviewStage,
    artifactId: string,
    notes: string,
  ) =>
    request<Project>(`/api/projects/${id}/workflow/review`, "POST", {
      stage,
      artifact_id: artifactId,
      notes,
    }),
  characters: (id: string, data: Character[]) =>
    request<Project>(`/api/projects/${id}/characters`, "PUT", data),
  uploadCharacter: (id: string, index: number, file: File) =>
    upload<Project>(`/api/projects/${id}/characters/${index}/reference`, file),
  shot: (id: string, sid: string, data: ShotInput) =>
    request<Project>(`/api/projects/${id}/shots/${sid}`, "PUT", data),
  batchDuration: (id: string, shotIds: string[], duration: number) =>
    request<Project>(`/api/projects/${id}/batch-shot-duration`, "PUT", {
      shot_ids: shotIds,
      duration,
    }),
  generate: (id: string, data: GenerateOptions) =>
    request<Project>(`/api/projects/${id}/generate`, "POST", data),
  selectCandidate: (
    id: string,
    sid: string,
    cid: string,
    subtitle?: string | null,
  ) =>
    request<Project>(`/api/projects/${id}/shots/${sid}/select`, "POST", {
      candidate_id: cid,
      ...(subtitle === undefined ? {} : { subtitle_text: subtitle }),
    }),
  selectFirst: (id: string) =>
    request<Project>(`/api/projects/${id}/select-first`, "POST", {}),
  reviewCandidate: (
    id: string,
    sid: string,
    cid: string,
    action: "reject" | "checked",
  ) =>
    request<Project>(
      `/api/projects/${id}/shots/${sid}/candidates/${cid}/review`,
      "POST",
      { action },
    ),
  resumeCandidate: (id: string, sid: string, cid: string) =>
    request<Project>(
      `/api/projects/${id}/shots/${sid}/candidates/${cid}/resume`,
      "POST",
      {},
    ),
  deleteFailed: (id: string, sid: string, cid: string) =>
    request<Project>(
      `/api/projects/${id}/shots/${sid}/candidates/${cid}`,
      "DELETE",
    ),
  trim: (id: string, sid: string, cid: string, data: ClipEdit) =>
    request<Project>(
      `/api/projects/${id}/shots/${sid}/candidates/${cid}/edit`,
      "PUT",
      data,
    ),
  uploadShot: (id: string, sid: string, kind: "visual" | "audio", file: File) =>
    upload<Project>(`/api/projects/${id}/shots/${sid}/upload/${kind}`, file),
  export: (
    id: string,
    kind: "animatic" | "preview" | "production",
    voice: boolean,
  ) => request<Project>(`/api/projects/${id}/export`, "POST", { kind, voice }),
  feedback: (id: string, eid: string, data: PublicationFeedback) =>
    request<Project>(
      `/api/projects/${id}/exports/${eid}/feedback`,
      "PUT",
      data,
    ),
};
function upload<T>(path: string, file: File) {
  const data = new FormData();
  data.append("file", file);
  return request<T>(path, "POST", data);
}
