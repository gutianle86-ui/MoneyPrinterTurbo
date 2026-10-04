export type StoryFormat = "dialogue" | "narration" | "mixed";
export type StyleMode = "auto" | "preset" | "custom";
export type ReviewStage = "content" | "preview" | "pilot";
export interface Character {
  name: string;
  appearance: string;
  voice: string;
  voice_description?: string;
  reference_uri?: string;
  reference_file?: string;
}
export interface ShotInput {
  title: string;
  scene: string;
  visual: string;
  narration: string;
  speaker: string;
  duration: number;
  characters: string[];
  purpose?: string;
  start_state?: string;
  end_state?: string;
  beat_index?: number | null;
  delivery?: string;
}
export interface ClipEdit {
  start: number;
  end: number | null;
}
export interface Candidate {
  id: string;
  provider: string;
  status: string;
  stale: boolean;
  file?: string | null;
  task_id?: string | null;
  estimated_cost?: number;
  created_at?: string;
  prompt?: string;
  subtitle_text?: string;
  edit?: ClipEdit;
  dialogue_requested?: boolean;
  request?: { model?: string };
}
export interface Shot extends ShotInput {
  id: string;
  approved: boolean;
  candidates: Candidate[];
  selected: string | null;
  audio: string | null;
}
export interface Script {
  title: string;
  hook: string;
  synopsis: string;
  characters: Character[];
  shots: ShotInput[];
}
export interface ScriptOption {
  id: string;
  source: string;
  script: Script;
}
export interface DramaBeat {
  scene: string;
  action: string;
  speaker: string;
  line: string;
  emotion: string;
}
export interface ContentBrief {
  format: StoryFormat;
  audience: string;
  source_notes: string;
  promise: string;
  opening: string;
  payoff: string;
  cliffhanger: string;
  narration: string;
  target_duration: number;
  beats: DramaBeat[];
}
export interface StylePreset {
  id: string;
  name: string;
  style: string;
  personal: boolean;
}
export interface StyleRecommendation {
  name: string;
  style: string;
  reason: string;
}
export interface WorkflowStatus {
  enabled: boolean;
  style_ok: boolean;
  content_ok: boolean;
  preview_ok: boolean;
  pilot_ok: boolean;
  blockers: string[];
  warnings: string[];
  story_revision: string;
  edit_revision: string;
}
export interface CostSummary {
  estimated_video_cost: number;
  selected_cost: number;
  unselected_cost: number;
  paid_attempts: number;
  multiple_candidate_shots: number;
  unsettled_tasks: number;
  shots: {
    shot_id: string;
    title: string;
    attempts: number;
    estimated_cost: number;
    selected_cost: number;
  }[];
}
export interface PublicationFeedback {
  platform: string;
  published_url: string;
  views: number | null;
  likes: number | null;
  conversions: number | null;
  revenue: number | null;
  actual_cost: number | null;
  notes: string;
}
export interface ExportRecord {
  id: string;
  file: string;
  subtitle: string;
  manifest: string;
  kind: string;
  duration: number;
  created_at: string;
  resolution?: string;
  current?: boolean;
  selected_candidates?: string[];
  story_revision?: string;
  edit_revision?: string;
  cost_summary?: CostSummary;
  feedback?: PublicationFeedback;
  audio_sources?: {
    shot_id: string;
    source: string;
    dialogue_requested?: boolean;
  }[];
}
export interface ProjectInput {
  title: string;
  premise: string;
  story_format: StoryFormat;
  style: string;
  style_mode: StyleMode;
  style_preset_id: string;
  budget: number;
}
export interface Project extends ProjectInput {
  id: string;
  created_at: string;
  updated_at: string;
  scripts: ScriptOption[];
  active_script: string | null;
  script_approved: boolean;
  characters: Character[];
  characters_approved: boolean;
  shots: Shot[];
  exports: ExportRecord[];
  reserved_cost: number;
  cost_summary: CostSummary;
  workflow?: { version: number; brief?: ContentBrief };
  workflow_status: WorkflowStatus;
  style_recommendation?: StyleRecommendation;
  job: {
    id?: string;
    status?: string;
    started_at?: string;
    finished_at?: string;
    message?: string;
    progress?: number;
  };
}
export interface ProjectListItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  budget: number;
  reserved_cost: number;
  shots: number;
  exports: number;
}
export interface Settings {
  llm_base_url: string;
  llm_model: string;
  llm_use_env_proxy: boolean;
  llm_api_key_configured: boolean;
  seedance_base_url: string;
  seedance_model: string;
  seedance_api_key_configured: boolean;
  estimate_per_second: number;
  seedance_estimates: Record<string, number>;
}
export type SettingsInput = Omit<
  Settings,
  "llm_api_key_configured" | "seedance_api_key_configured"
> & { llm_api_key: string; seedance_api_key: string };
export interface VideoProfile {
  label: string;
  min_duration: number;
  max_duration: number;
  default_estimate: number;
  resolution: string;
}
export interface WorkbenchStatus {
  settings: Settings;
  video_models: Record<string, VideoProfile>;
  local_voice: boolean;
  storage: string;
  style_presets: StylePreset[];
}
export interface GenerateOptions {
  shot_ids: string[];
  mode: "preview" | "seedance";
  variants: number;
  confirm_paid: boolean;
}
export type DialogState =
  | { kind: "project"; edit?: boolean }
  | { kind: "settings" }
  | { kind: "brief" }
  | { kind: "script"; id?: string }
  | { kind: "shot"; id: string }
  | { kind: "candidate"; shotId: string; candidateId: string }
  | { kind: "comparison"; shotId: string }
  | { kind: "trim"; shotId: string; candidateId: string }
  | { kind: "review"; stage: ReviewStage; artifactId?: string }
  | { kind: "batch" }
  | { kind: "feedback"; id: string }
  | {
      kind: "generate";
      options: GenerateOptions;
      revision: string;
      model: string;
      rate: number;
    }
  | { kind: "switch-script"; id: string }
  | { kind: "delete-failed"; shotId: string; candidateId: string };
