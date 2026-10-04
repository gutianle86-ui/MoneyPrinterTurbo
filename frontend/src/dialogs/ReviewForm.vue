<script setup lang="ts">
import { ref } from "vue";
import { useStudio } from "../composables/useStudio";
import type { ReviewStage } from "../types";
const props = defineProps<{ stage: ReviewStage; artifactId?: string }>();
const { project, state, locked, act, api, closeDialog } = useStudio();
const notes = ref(""),
  checked = ref(false);
const hints = {
  content:
    "核对原文事实、人物关系和台词归属；按角色试读，确认动作推动剧情、反差已兑现、结尾有悬念。",
  preview: "观看完整预演，确认信息能听懂、看点出现够早、前后镜头讲得通。",
  pilot:
    "观看候选视频，确认人物、画风、动作、说话人、中文口型、音色和起止状态可用。通过后才开放批量制作。",
};
async function save() {
  if (
    await act(
      (pid) =>
        api.reviewWorkflow(
          pid,
          props.stage,
          props.artifactId || "",
          notes.value,
        ),
      props.stage === "preview" ? 3 : undefined,
    )
  ) {
    if (props.stage === "preview" && project.value.workflow_status.preview_ok) {
      state.selectedShots = new Set(
        project.value.shots.slice(0, 1).map((s) => s.id),
      );
      state.variants = 1;
      state.generateMode = "seedance";
    }
    closeDialog();
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <p class="muted">{{ hints[stage] }}</p>
    <label class="check-label" style="margin: 20px 0"
      ><input
        v-model="checked"
        type="checkbox"
        required
        :disabled="locked"
      />我已完成上述检查，愿意继续下一步</label
    >
    <div class="field">
      <label class="label" for="review-notes">判断依据（至少 5 字）</label
      ><textarea
        id="review-notes"
        v-model="notes"
        minlength="5"
        maxlength="1000"
        rows="3"
        required
        :disabled="locked"
        placeholder="写明为什么通过，例如开头直接呈现反差、人物和动作符合设定"
      ></textarea>
    </div>
    <p class="hint">这是人工审核记录，不是 AI 对质量或播放量的保证。</p>
    <div class="dialog-actions">
      <button class="button" :disabled="locked">记录通过</button>
    </div>
  </form>
</template>
