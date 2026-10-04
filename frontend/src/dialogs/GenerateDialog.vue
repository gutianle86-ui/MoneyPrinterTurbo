<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import { modelProfile, money, validCandidates } from "../domain";
import type { GenerateOptions } from "../types";
const props = defineProps<{
  options: GenerateOptions;
  revision: string;
  model: string;
  rate: number;
}>();
const { project, state, locked, act, api, notify, closeDialog } = useStudio();
const shots = computed(() =>
  project.value.shots.filter((s) => props.options.shot_ids.includes(s.id)),
);
const cost = computed(
  () =>
    shots.value.reduce((sum, s) => sum + s.duration, 0) *
    props.options.variants *
    props.rate,
);
const remaining = computed(() =>
  Math.max(0, project.value.budget - project.value.reserved_cost),
);
const existing = computed(() =>
  shots.value.filter((s) => validCandidates(s).length),
);
const changed = computed(
  () =>
    props.revision !== project.value.workflow_status.story_revision ||
    props.model !== state.status?.settings.seedance_model ||
    props.rate !== state.status.settings.estimate_per_second,
);
async function submit() {
  if (changed.value) {
    notify("项目或模型设置已变化，请重新检查制作清单", true);
    closeDialog();
    return;
  }
  if (await act((pid) => api.generate(pid, props.options))) closeDialog();
}
</script>
<template>
  <p class="muted">
    {{ modelProfile(state.status, model)?.label || model }} ·
    {{ shots.length }} 个镜头 × {{ options.variants }} 个候选
  </p>
  <div class="stats">
    <div class="stat">
      <span>本次生成预估</span><b>{{ money(cost) }}</b>
    </div>
    <div class="stat">
      <span>项目剩余预算</span><b>{{ money(remaining) }}</b>
    </div>
  </div>
  <div v-if="existing.length" class="info amber">
    {{
      existing.length
    }}
    个镜头已有有效候选，继续制作会增加费用。可先对比现有候选，再决定是否重做。
  </div>
  <ul class="workflow-list">
    <li v-for="shot in shots" :key="shot.id">
      {{ shot.title }} · {{ shot.duration }} 秒{{
        validCandidates(shot).length
          ? ` · 已有 ${validCandidates(shot).length} 个有效候选`
          : ""
      }}
    </li>
  </ul>
  <details v-if="project.workflow_status.warnings.length">
    <summary>
      节奏与衔接提示（{{ project.workflow_status.warnings.length }}）
    </summary>
    <ul class="workflow-list">
      <li v-for="warning in project.workflow_status.warnings" :key="warning">
        {{ warning }}
      </li>
    </ul>
  </details>
  <p v-if="changed" class="hint">项目或模型设置已变化，请返回重新检查。</p>
  <p v-if="cost > remaining" class="hint">
    本次预估超过剩余预算，请减少镜头或候选数。
  </p>
  <p class="hint">
    这是视频预算估算，文本和人工费用未计入。提交后将开始付费任务；已有素材保留。
  </p>
  <div class="dialog-actions">
    <button
      class="button ghost"
      :disabled="state.requestPending"
      @click="closeDialog"
    >
      返回检查</button
    ><button
      class="button"
      :disabled="locked || changed || cost > remaining || !shots.length"
      @click="submit"
    >
      提交本次付费制作
    </button>
  </div>
</template>
