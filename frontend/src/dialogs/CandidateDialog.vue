<script setup lang="ts">
import { computed, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { isVideo } from "../domain";
import MediaPreview from "../components/MediaPreview.vue";
import Badge from "../components/Badge.vue";
const props = defineProps<{ shotId: string; candidateId: string }>();
const { project, locked, openDialog, closeDialog, act, api } = useStudio();
const shot = computed(() =>
  project.value.shots.find((s) => s.id === props.shotId)!,
);
const candidate = computed(() =>
  shot.value.candidates.find((c) => c.id === props.candidateId)!,
);
const subtitle = ref(candidate.value.subtitle_text ?? shot.value.narration);
async function choose() {
  if (
    await act((pid) =>
      api.selectCandidate(
        pid,
        props.shotId,
        props.candidateId,
        subtitle.value === shot.value.narration ? null : subtitle.value,
      ),
    )
  )
    closeDialog();
}
async function review(action: "reject" | "checked") {
  if (
    await act((pid) =>
      api.reviewCandidate(pid, props.shotId, props.candidateId, action),
    )
  )
    closeDialog();
}
async function resume() {
  if (
    await act((pid) =>
      api.resumeCandidate(pid, props.shotId, props.candidateId),
    )
  )
    closeDialog();
}
</script>
<template>
  <MediaPreview :candidate="candidate" class="dialog-media" />
  <div class="meta-row">
    <Badge>{{
      candidate.provider === "preview"
        ? "本地文字预演"
        : candidate.provider === "upload"
          ? "导入素材"
          : "AI 视频"
    }}</Badge
    ><Badge :tone="candidate.stale ? 'amber' : ''">{{
      candidate.stale ? "设定已变更，候选过期" : candidate.status
    }}</Badge>
  </div>
  <div v-if="candidate.status === 'ready'" class="field">
    <label class="label" for="candidate-subtitle"
      >成片字幕（按实际听到的台词校对）</label
    ><textarea
      id="candidate-subtitle"
      v-model="subtitle"
      rows="2"
      maxlength="300"
      :disabled="locked"
    ></textarea>
    <p class="hint">
      选用时保存字幕；这不会修改音频。{{
        candidate.edit
          ? `当前剪辑：${candidate.edit.start} 秒 → ${candidate.edit.end ?? "末尾"}`
          : "当前保留完整素材"
      }}
    </p>
  </div>
  <p v-if="candidate.task_id" class="hint">远端任务：{{ candidate.task_id }}</p>
  <p v-if="candidate.prompt" class="hint">{{ candidate.prompt }}</p>
  <div class="dialog-actions">
    <button
      v-if="
        candidate.status === 'failed' && !candidate.task_id && !candidate.file
      "
      class="button ghost"
      :disabled="locked"
      @click="openDialog({ kind: 'delete-failed', shotId, candidateId })"
    >
      删除失败记录</button
    ><button
      v-if="['uncertain', 'interrupted'].includes(candidate.status)"
      class="button ghost"
      :disabled="locked"
      @click="review('checked')"
    >
      已在后台核对，解除重试限制</button
    ><button
      v-if="
        candidate.task_id &&
        ['interrupted', 'checked', 'failed'].includes(candidate.status)
      "
      class="button secondary"
      :disabled="locked"
      @click="resume"
    >
      继续查询原任务</button
    ><template v-if="candidate.status === 'ready'"
      ><template v-if="isVideo(candidate)"
        ><button
          class="button secondary"
          :disabled="locked || candidate.stale"
          @click="openDialog({ kind: 'trim', shotId, candidateId })"
        >
          剪辑入点 / 出点</button
        ><button
          v-if="project.workflow_status.enabled"
          class="button secondary"
          :disabled="locked || candidate.stale"
          @click="
            openDialog({
              kind: 'review',
              stage: 'pilot',
              artifactId: candidateId,
            })
          "
        >
          记录样片审核
        </button></template
      ><button
        class="button ghost"
        :disabled="locked"
        @click="review('reject')"
      >
        淘汰</button
      ><button
        class="button"
        :disabled="locked || candidate.stale"
        @click="choose"
      >
        选用这个候选
      </button></template
    >
  </div>
</template>
