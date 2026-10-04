import type {
  Candidate,
  ExportRecord,
  Project,
  Shot,
  WorkbenchStatus,
} from "./types";

export const steps = [
  "内容策划与剧本",
  "角色设定",
  "分镜与免费预演",
  "样片与镜头制作",
  "剪辑与导出",
];
export const formatLabels = {
  dialogue: "对话短剧",
  narration: "旁白推文",
  mixed: "混合形式",
};
export const textModels: Record<string, string> = {
  "deepseek-v4-pro": "DeepSeek Pro",
  "deepseek-flash": "DeepSeek Flash",
};
export const money = (value: number | undefined) =>
  `¥${Number(value || 0).toFixed(2)}`;
export const dateText = (value: string) =>
  new Date(value).toLocaleString("zh-CN");
export const validCandidates = (shot: Shot) =>
  shot.candidates.filter((c) => c.status === "ready" && !c.stale);
export const picked = (shot: Shot) =>
  validCandidates(shot).find((c) => c.id === shot.selected);
export const isVideo = (candidate: Candidate) =>
  /\.(mp4|mov)$/i.test(candidate.file || "");
export const projectFormat = (p: Project) =>
  p.story_format || p.workflow?.brief?.format || "narration";
export const hasBrief = (p: Project) =>
  Boolean(
    p.workflow?.brief?.narration?.trim() || p.workflow?.brief?.beats?.length,
  );
export const modelProfile = (status: WorkbenchStatus | null, model?: string) =>
  Object.entries(status?.video_models || {}).find(([id]) =>
    (model || status?.settings.seedance_model || "").startsWith(
      id.replace(/-[^-]+$/, "") + "-",
    ),
  )?.[1];
export function isCurrentExport(p: Project, entry: ExportRecord) {
  if (entry.kind === "animatic") return false;
  if (entry.current !== undefined) return entry.current;
  const candidates = p.shots.map(picked);
  if (!candidates.length || candidates.some((c) => !c)) return false;
  if (entry.selected_candidates?.length)
    return (
      entry.selected_candidates.length === candidates.length &&
      entry.selected_candidates.every(
        (id, index) => id === candidates[index]?.id,
      )
    );
  return candidates.length === 1 && candidates[0]?.file === entry.file;
}
export const briefFields = [
  { key: "audience", label: "给谁看", max: 300 },
  { key: "source_notes", label: "原文依据与待核对项", max: 3000 },
  { key: "promise", label: "核心反差", max: 500 },
  { key: "opening", label: "选定开头", max: 500 },
  { key: "payoff", label: "本条要兑现的看点", max: 500 },
  { key: "cliffhanger", label: "结尾留下的具体问题", max: 500 },
  { key: "narration", label: "完整口播文案", max: 3000 },
] as const;
