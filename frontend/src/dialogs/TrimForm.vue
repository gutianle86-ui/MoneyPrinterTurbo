<script setup lang="ts">
import { ref } from "vue";
import { useStudio } from "../composables/useStudio";
const props = defineProps<{ shotId: string; candidateId: string }>();
const { project, locked, asset, act, api, closeDialog } = useStudio();
const candidate = project.value.shots
  .find((s) => s.id === props.shotId)!
  .candidates.find((c) => c.id === props.candidateId)!;
const start = ref(candidate.edit?.start || 0),
  end = ref<string | number>(candidate.edit?.end ?? ""),
  duration = ref(0);
async function save() {
  if (
    await act((pid) =>
      api.trim(pid, props.shotId, props.candidateId, {
        start: start.value,
        end: end.value === "" ? null : Number(end.value),
      }),
    )
  )
    closeDialog();
}
</script>
<template>
  <form @submit.prevent="save">
    <video
      class="dialog-media"
      :src="asset(candidate.file!)"
      controls
      playsinline
      preload="metadata"
      @loadedmetadata="duration = ($event.target as HTMLVideoElement).duration"
    ></video>
    <p class="hint">
      {{
        duration
          ? `素材时长 ${duration.toFixed(2)} 秒。保存后需重新合成。`
          : "播放素材，确定需要保留的区间。"
      }}
    </p>
    <div class="grid two">
      <div class="field">
        <label class="label" for="clip-start">入点（秒）</label
        ><input
          id="clip-start"
          v-model.number="start"
          type="number"
          min="0"
          step="0.01"
          required
          :disabled="locked"
        />
      </div>
      <div class="field">
        <label class="label" for="clip-end">出点（秒，留空保留到末尾）</label
        ><input
          id="clip-end"
          v-model="end"
          type="number"
          min="0.01"
          step="0.01"
          :disabled="locked"
        />
      </div>
    </div>
    <p class="hint">
      画面和原声一起裁剪。请勿切断对白；外部配音长于区间时，合成会提示调整。入点为
      0、出点留空可恢复完整素材。
    </p>
    <div class="dialog-actions">
      <button class="button" :disabled="locked">保存剪辑区间</button>
    </div>
  </form>
</template>
