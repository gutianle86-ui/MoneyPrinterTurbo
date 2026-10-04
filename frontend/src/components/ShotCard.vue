<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import { picked, validCandidates } from "../domain";
import type { Shot } from "../types";
import Badge from "./Badge.vue";
import MediaPreview from "./MediaPreview.vue";
import UploadButton from "./UploadButton.vue";
const props = defineProps<{ shot: Shot; index: number }>();
const { state, locked, asset, openDialog, act, api, notify } = useStudio();
const chosen = computed(() => picked(props.shot));
const candidates = computed(() => validCandidates(props.shot));
const display = computed(() => chosen.value || candidates.value[0]);
const statuses: Record<string, string> = {
  ready: "可选",
  generating: "制作中",
  failed: "失败",
  interrupted: "待查询",
  uncertain: "待核对",
  rejected: "淘汰",
  checked: "已核对",
};
function toggle(checked: boolean) {
  if (checked) state.selectedShots.add(props.shot.id);
  else state.selectedShots.delete(props.shot.id);
}
async function upload(kind: "visual" | "audio", file: File) {
  if (await act((pid) => api.uploadShot(pid, props.shot.id, kind, file)))
    notify("素材已导入");
}
</script>
<template>
  <article
    class="shot-card"
    :class="{ selected: chosen }"
    :id="`shot-${shot.id}`"
  >
    <div class="shot-top">
      <input
        type="checkbox"
        :aria-label="`选择镜头 ${index + 1}`"
        :checked="state.selectedShots.has(shot.id)"
        :disabled="locked"
        @change="toggle(($event.target as HTMLInputElement).checked)"
      /><span class="index">{{ String(index + 1).padStart(2, "0") }}</span
      ><strong>{{ shot.title }}</strong
      ><Badge :tone="chosen ? 'green' : ''">{{
        chosen ? "已选用" : candidates.length ? "待筛选" : "未制作"
      }}</Badge>
    </div>
    <div class="shot-preview">
      <MediaPreview v-if="display" :candidate="display" />
      <div v-else class="no-frame">
        <span class="frame-index">{{ String(index + 1).padStart(2, "0") }}</span
        >等待第一个画面<br />{{ shot.scene }}
      </div>
    </div>
    <div class="shot-body">
      <p>
        {{
          shot.narration
            ? `${shot.speaker}：${shot.narration}`
            : "无台词 · 动作 / 反应"
        }}
      </p>
      <div class="candidate-strip">
        <button
          v-for="(c, i) in shot.candidates"
          :key="c.id"
          class="candidate-button"
          :class="{ picked: c.id === shot.selected }"
          :aria-label="`查看镜头 ${index + 1} 的候选 ${i + 1}`"
          @click="
            openDialog({
              kind: 'candidate',
              shotId: shot.id,
              candidateId: c.id,
            })
          "
        >
          <img
            v-if="c.file && /\.(png|jpg|jpeg|webp)$/i.test(c.file)"
            :src="asset(c.file)"
            :alt="`候选 ${i + 1}`"
          /><span v-else class="candidate-symbol">▷</span
          ><span
            >V{{ i + 1 }} ·
            {{ c.stale ? "已过期" : statuses[c.status] || c.status }}</span
          >
        </button>
      </div>
      <div class="shot-actions">
        <button
          v-if="candidates.length >= 2"
          class="button secondary"
          @click="openDialog({ kind: 'comparison', shotId: shot.id })"
        >
          并排对比候选</button
        ><UploadButton
          accept=".mp4,.mov,.png,.jpg,.jpeg,.webp"
          label="导入画面"
          :upload="(file) => upload('visual', file)"
        /><UploadButton
          accept=".mp3,.wav,.m4a,.aiff"
          :label="shot.audio ? '替换音轨' : '导入音轨'"
          :upload="(file) => upload('audio', file)"
        /><button
          class="button ghost"
          :disabled="locked"
          @click="openDialog({ kind: 'shot', id: shot.id })"
        >
          编辑分镜
        </button>
      </div>
      <audio
        v-if="shot.audio"
        :src="asset(shot.audio)"
        controls
        preload="none"
        style="width: 100%; height: 30px; margin-top: 12px"
      ></audio>
    </div>
  </article>
</template>
