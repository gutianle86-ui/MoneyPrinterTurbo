import { computed, nextTick, reactive, shallowRef } from "vue";
import { api, ApiError } from "../api";
import { isCurrentExport, picked, textModels } from "../domain";
import type {
  DialogState,
  Project,
  ProjectListItem,
  SettingsInput,
  WorkbenchStatus,
} from "../types";

const state = reactive({
  project: null as Project | null,
  projects: [] as ProjectListItem[],
  status: null as WorkbenchStatus | null,
  stage: 0,
  selectedShots: new Set<string>(),
  batchShots: new Set<string>(),
  requestPending: false,
  generateMode: "preview" as "preview" | "seedance",
  variants: 1,
  shotFilter: "all",
  loading: true,
  loadError: "",
  notice: null as { message: string; error: boolean } | null,
});
const dialog = shallowRef<DialogState | null>(null);
const dialogProjectId = shallowRef<string | null>(null);
const project = computed(() => state.project!);
const busy = computed(() => state.project?.job?.status === "running");
const locked = computed(
  () => state.loading || busy.value || state.requestPending,
);
const activeScript = computed(
  () =>
    state.project?.scripts.find((s) => s.id === state.project?.active_script)
      ?.script,
);
const selectedCount = computed(
  () => state.project?.shots.filter(picked).length || 0,
);
const canMake = computed(() =>
  Boolean(
    state.project?.shots.length &&
    state.project.script_approved &&
    state.project.characters_approved &&
    state.project.shots.every((s) => s.approved),
  ),
);
const done = computed(() => {
  const p = state.project;
  return p
    ? [
        p.script_approved &&
          (!p.workflow_status.enabled || p.workflow_status.content_ok),
        p.characters_approved,
        p.shots.length > 0 && p.shots.every((s) => s.approved),
        p.shots.length > 0 && selectedCount.value === p.shots.length,
        p.exports.some((e) => isCurrentExport(p, e)),
      ]
    : [];
});
let noticeTimer: ReturnType<typeof setTimeout> | undefined;
let pollTimer: ReturnType<typeof setTimeout> | undefined;
let epoch = 0,
  projectTicket = 0,
  stopped = true;

function notify(message: string, error = false) {
  clearTimeout(noticeTimer);
  state.notice = { message, error };
  noticeTimer = setTimeout(
    () => {
      state.notice = null;
    },
    error ? 10000 : 4000,
  );
}
function failure(error: unknown) {
  notify(
    error instanceof Error ? error.message : "操作失败，请检查本地服务",
    true,
  );
}
function openDialog(value: DialogState) {
  dialogProjectId.value = state.project?.id || null;
  dialog.value = value;
}
function closeDialog() {
  dialog.value = null;
  dialogProjectId.value = null;
}
function asset(file: string, pid = state.project?.id) {
  return `/assets/${pid}/${file}`;
}
function navigate(stage: number) {
  state.stage = stage;
  if (state.project)
    localStorage.setItem(`drama-stage-${state.project.id}`, String(stage));
  window.scrollTo({ top: 0, behavior: "smooth" });
}
async function reloadProjects() {
  state.projects = await api.projects();
}
async function openProject(id: string) {
  const ticket = ++projectTicket;
  epoch++;
  const result = await api.project(id);
  if (ticket !== projectTicket) return;
  closeDialog();
  state.project = result;
  state.selectedShots = new Set(
    result.shots.filter((s) => !picked(s)).map((s) => s.id),
  );
  state.batchShots.clear();
  localStorage.setItem("drama-project", id);
  const saved = Number(localStorage.getItem(`drama-stage-${id}`));
  state.stage = Number.isInteger(saved) && saved >= 0 && saved < 5 ? saved : 0;
}
async function changeProject(id: string) {
  if (!id || state.requestPending) return;
  try {
    await openProject(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) await syncProjects();
    else failure(error);
  }
}
async function syncProjects() {
  const ticket = projectTicket;
  await reloadProjects();
  if (
    ticket !== projectTicket ||
    state.requestPending ||
    !state.project ||
    state.projects.some((p) => p.id === state.project?.id)
  )
    return;
  localStorage.removeItem(`drama-stage-${state.project.id}`);
  localStorage.removeItem("drama-project");
  epoch++;
  state.project = null;
  state.selectedShots.clear();
  state.batchShots.clear();
  state.stage = 0;
  closeDialog();
  if (state.projects[0]) await openProject(state.projects[0].id);
  notify("当前项目已移除，项目列表已更新");
}
async function act(
  operation: (pid: string) => Promise<Project>,
  next?: number,
): Promise<boolean> {
  if (locked.value || !state.project) return false;
  if (dialog.value && dialogProjectId.value !== state.project.id) {
    closeDialog();
    return false;
  }
  state.requestPending = true;
  epoch++;
  const pid = state.project.id;
  try {
    const result = await operation(pid);
    if (state.project?.id !== pid) return false;
    state.project = result;
    state.selectedShots = new Set(
      [...state.selectedShots].filter((id) =>
        result.shots.some((s) => s.id === id),
      ),
    );
    state.batchShots = new Set(
      [...state.batchShots].filter((id) =>
        result.shots.some((s) => s.id === id),
      ),
    );
    if (next !== undefined) navigate(next);
    if (result.job.status === "running") {
      await nextTick();
      document
        .getElementById("job-panel")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    return true;
  } catch (error) {
    failure(error);
    return false;
  } finally {
    state.requestPending = false;
    epoch++;
  }
}
async function guarded(operation: () => Promise<void>): Promise<boolean> {
  if (locked.value) return false;
  state.requestPending = true;
  epoch++;
  try {
    await operation();
    return true;
  } catch (error) {
    failure(error);
    return false;
  } finally {
    state.requestPending = false;
    epoch++;
  }
}
function settingsInput(): SettingsInput {
  const {
    llm_api_key_configured: _llm,
    seedance_api_key_configured: _video,
    ...settings
  } = state.status!.settings;
  return { ...settings, llm_api_key: "", seedance_api_key: "" };
}
async function switchModel(kind: "text" | "video", model: string) {
  if (!state.status) return;
  await guarded(async () => {
    const settings = settingsInput();
    if (kind === "text") {
      if (!textModels[model]) return;
      settings.llm_model = model;
    } else {
      const profile = state.status!.video_models[model];
      if (!profile) return;
      settings.seedance_model = model;
      settings.estimate_per_second =
        settings.seedance_estimates[model] ?? profile.default_estimate;
    }
    state.status!.settings = await api.settings(settings);
    notify(
      `已切换到 ${kind === "text" ? textModels[model] : state.status!.video_models[model].label}，用于后续制作`,
    );
  });
}
async function showSettings() {
  if (
    await guarded(async () => {
      state.status = await api.status();
    })
  )
    openDialog({ kind: "settings" });
}
async function showProject(edit = false) {
  if (!state.status) return;
  if (
    await guarded(async () => {
      state.status!.style_presets = await api.stylePresets();
    })
  )
    openDialog({ kind: "project", edit });
}
async function poll() {
  if (stopped) return;
  try {
    if (
      !state.requestPending &&
      (busy.value || document.visibilityState === "visible")
    ) {
      await syncProjects();
      if (state.project && !state.requestPending) {
        const pid = state.project.id,
          token = epoch,
          previous = state.project.job;
        const updated = await api.project(pid);
        // A delayed poll must never replace a newer edit, selection or project.
        if (
          !stopped &&
          !state.requestPending &&
          epoch === token &&
          state.project?.id === pid
        ) {
          state.project = updated;
          if (
            previous.id !== updated.job.id ||
            previous.status !== updated.job.status
          ) {
            await reloadProjects();
            if (updated.job.status === "done")
              notify(updated.job.message || "处理完成，可以继续筛选或导出");
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      try {
        await syncProjects();
      } catch {
        failure(error);
      }
    } else notify("与工作台的连接中断，请检查本地服务是否仍在运行。", true);
  }
  if (!stopped) pollTimer = setTimeout(poll, busy.value ? 1500 : 5000);
}
async function init() {
  stopped = false;
  state.loading = true;
  state.loadError = "";
  try {
    state.status = await api.status();
    await reloadProjects();
    const remembered = localStorage.getItem("drama-project");
    const id =
      state.projects.find((p) => p.id === remembered)?.id ||
      state.projects[0]?.id;
    if (id) await openProject(id);
    pollTimer = setTimeout(poll, 1500);
  } catch (error) {
    state.loadError = error instanceof Error ? error.message : "连接工作台失败";
  } finally {
    state.loading = false;
  }
}
function stop() {
  stopped = true;
  epoch++;
  clearTimeout(pollTimer);
  clearTimeout(noticeTimer);
}
if (import.meta.hot) import.meta.hot.dispose(stop);

export function useStudio() {
  return {
    state,
    project,
    busy,
    locked,
    activeScript,
    selectedCount,
    canMake,
    done,
    dialog,
    dialogProjectId,
    api,
    asset,
    notify,
    failure,
    openDialog,
    closeDialog,
    navigate,
    reloadProjects,
    openProject,
    changeProject,
    act,
    guarded,
    settingsInput,
    switchModel,
    showSettings,
    showProject,
    init,
    stop,
    poll,
  };
}
