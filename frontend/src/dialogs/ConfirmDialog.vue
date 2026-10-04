<script setup lang="ts">
import { useStudio } from "../composables/useStudio";
const props = defineProps<{
  kind: "switch-script" | "delete-failed";
  id?: string;
  shotId?: string;
  candidateId?: string;
}>();
const { project, state, locked, act, api, closeDialog, notify } = useStudio();
async function confirm() {
  const ok =
    props.kind === "switch-script"
      ? await act((pid) => api.selectScript(pid, props.id!))
      : await act((pid) =>
          api.deleteFailed(pid, props.shotId!, props.candidateId!),
        );
  if (ok) {
    if (props.kind === "switch-script") {
      state.selectedShots = new Set(project.value.shots.map((s) => s.id));
      state.batchShots.clear();
    } else notify("失败记录已删除");
    closeDialog();
  }
}
</script>
<template>
  <p class="muted">
    {{
      kind === "switch-script"
        ? "当前角色与镜头会归档，新的方案需要重新审核和制作。历史文件与导出仍会保留。"
        : "只会删除这条没有生成视频、没有远程任务编号的失败候选，不影响剧本、角色图、分镜或预算。"
    }}
  </p>
  <div class="dialog-actions">
    <button
      class="button ghost"
      :disabled="state.requestPending"
      @click="closeDialog"
    >
      取消</button
    ><button class="button" :disabled="locked" @click="confirm">
      {{ kind === "switch-script" ? "切换方案" : "确认删除" }}
    </button>
  </div>
</template>
