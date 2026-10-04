<script setup lang="ts">
import { computed, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { validCandidates } from "../domain";
const { project, state, locked, act, api, notify, closeDialog } = useStudio();
const shots = project.value.shots.filter((s) => state.batchShots.has(s.id));
const duration = ref(shots[0]?.duration || 6);
const changed = computed(() =>
  shots.filter((s) => s.duration !== duration.value),
);
const stale = computed(() =>
  changed.value.reduce((sum, s) => sum + validCandidates(s).length, 0),
);
async function save() {
  if (
    await act((pid) =>
      api.batchDuration(
        pid,
        shots.map((s) => s.id),
        duration.value,
      ),
    )
  ) {
    state.batchShots.clear();
    closeDialog();
    notify("分镜时长已保存，请检查变化的镜头并重新审核");
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <p class="muted">
      已选择 {{ shots.length }} 个镜头：{{
        shots.map((s) => s.title).join("、")
      }}
    </p>
    <label class="label" for="batch-duration">统一计划时长（2–12 秒）</label
    ><input
      id="batch-duration"
      v-model.number="duration"
      type="number"
      min="2"
      max="12"
      step="1"
      required
      :disabled="locked"
    />
    <p class="hint">
      将修改 {{ changed.length }} 个镜头，{{
        stale
      }}
      个有效候选会过期。所选镜头总时长
      {{ shots.reduce((sum, s) => sum + s.duration, 0) }} 秒 →
      {{ shots.length * duration }} 秒。
    </p>
    <p class="hint">
      只有时长变化的镜头会撤销审核、使旧候选过期并解除上传音轨关联；旧文件保留。保存后请重新预演和审核。
    </p>
    <div class="dialog-actions">
      <button
        type="button"
        class="button ghost"
        :disabled="state.requestPending"
        @click="closeDialog"
      >
        取消</button
      ><button class="button" :disabled="locked || !shots.length">
        保存所选镜头
      </button>
    </div>
  </form>
</template>
