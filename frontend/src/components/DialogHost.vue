<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import ProjectForm from "../dialogs/ProjectForm.vue";
import SettingsForm from "../dialogs/SettingsForm.vue";
import BriefForm from "../dialogs/BriefForm.vue";
import ScriptForm from "../dialogs/ScriptForm.vue";
import ShotForm from "../dialogs/ShotForm.vue";
import CandidateDialog from "../dialogs/CandidateDialog.vue";
import ComparisonDialog from "../dialogs/ComparisonDialog.vue";
import TrimForm from "../dialogs/TrimForm.vue";
import ReviewForm from "../dialogs/ReviewForm.vue";
import BatchDurationForm from "../dialogs/BatchDurationForm.vue";
import FeedbackForm from "../dialogs/FeedbackForm.vue";
import GenerateDialog from "../dialogs/GenerateDialog.vue";
import ConfirmDialog from "../dialogs/ConfirmDialog.vue";
const { dialog, project, state, closeDialog } = useStudio();
const d = computed(() => dialog.value!);
const root = ref<HTMLDialogElement | null>(null);
const title = computed(() => {
  const value = d.value;
  if (value.kind === "project") return value.edit ? "项目设置" : "创建新项目";
  if (value.kind === "review")
    return { content: "剧本审核", preview: "预演审核", pilot: "样片审核" }[
      value.stage
    ];
  if (value.kind === "shot")
    return `编辑镜头 · ${project.value.shots.find((s) => s.id === value.id)?.title || ""}`;
  if (value.kind === "candidate" || value.kind === "comparison") {
    const shot = project.value.shots.find((s) => s.id === value.shotId);
    return value.kind === "comparison"
      ? `候选对比 · ${shot?.title || ""}`
      : `候选 ${(shot?.candidates.findIndex((c) => c.id === value.candidateId) ?? 0) + 1} · ${shot?.title || ""}`;
  }
  return {
    settings: "生成服务设置",
    brief: "内容策划",
    script: "编辑剧本副本",
    trim: "剪辑片段 · 原素材保留",
    batch: "批量修改分镜时长",
    feedback: "发布效果与实际成本",
    generate: "本次付费制作清单",
    "switch-script": "切换剧本方案",
    "delete-failed": "删除失败记录",
  }[value.kind];
});
function pause() {
  root.value
    ?.querySelectorAll<HTMLMediaElement>("video,audio")
    .forEach((media) => media.pause());
}
function dismiss() {
  if (state.requestPending) return;
  pause();
  closeDialog();
}
onMounted(async () => {
  await nextTick();
  root.value?.showModal();
});
onBeforeUnmount(pause);
</script>
<template>
  <Teleport to="body"
    ><dialog
      ref="root"
      :class="{ 'comparison-dialog': d.kind === 'comparison' }"
      aria-labelledby="dialog-title"
      @cancel.prevent="dismiss"
    >
      <div class="dialog-head">
        <h2 id="dialog-title">{{ title }}</h2>
        <button
          class="close"
          aria-label="关闭"
          :disabled="state.requestPending"
          @click="dismiss"
        >
          ×
        </button>
      </div>
      <div :key="JSON.stringify(d)">
        <ProjectForm v-if="d.kind === 'project'" :edit="d.edit" /><SettingsForm
          v-else-if="d.kind === 'settings'"
        /><BriefForm v-else-if="d.kind === 'brief'" /><ScriptForm
          v-else-if="d.kind === 'script'"
          :id="d.id"
        /><ShotForm v-else-if="d.kind === 'shot'" :id="d.id" /><CandidateDialog
          v-else-if="d.kind === 'candidate'"
          :shot-id="d.shotId"
          :candidate-id="d.candidateId"
        /><ComparisonDialog
          v-else-if="d.kind === 'comparison'"
          :shot-id="d.shotId"
        /><TrimForm
          v-else-if="d.kind === 'trim'"
          :shot-id="d.shotId"
          :candidate-id="d.candidateId"
        /><ReviewForm
          v-else-if="d.kind === 'review'"
          :stage="d.stage"
          :artifact-id="d.artifactId"
        /><BatchDurationForm v-else-if="d.kind === 'batch'" /><FeedbackForm
          v-else-if="d.kind === 'feedback'"
          :id="d.id"
        /><GenerateDialog
          v-else-if="d.kind === 'generate'"
          :options="d.options"
          :revision="d.revision"
          :model="d.model"
          :rate="d.rate"
        /><ConfirmDialog
          v-else-if="d.kind === 'switch-script'"
          kind="switch-script"
          :id="d.id"
        /><ConfirmDialog
          v-else-if="d.kind === 'delete-failed'"
          kind="delete-failed"
          :shot-id="d.shotId"
          :candidate-id="d.candidateId"
        />
      </div></dialog
  ></Teleport>
</template>
