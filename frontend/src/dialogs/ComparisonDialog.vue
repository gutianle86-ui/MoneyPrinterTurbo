<script setup lang="ts">
import { computed, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { money, validCandidates } from "../domain";
import MediaPreview from "../components/MediaPreview.vue";
const props = defineProps<{ shotId: string }>();
const { project, locked, notify, openDialog, act, api, closeDialog } =
  useStudio();
const shot = computed(() =>
  project.value.shots.find((s) => s.id === props.shotId)!,
);
const candidates = computed(() => validCandidates(shot.value));
const left =
  shot.value.selected &&
  candidates.value.some((c) => c.id === shot.value.selected)
    ? shot.value.selected
    : candidates.value[0]?.id || "";
const pair = ref([left, candidates.value.find((c) => c.id !== left)?.id || ""]);
const selected = computed(() =>
  pair.value.map((id) => candidates.value.find((c) => c.id === id)),
);
const sound = ref("0");
const players = ref<InstanceType<typeof MediaPreview>[]>([]);
function change(side: number, id: string) {
  const old = pair.value[side];
  pair.value[side] = id;
  if (pair.value[1 - side] === id) pair.value[1 - side] = old;
}
async function play() {
  const results = await Promise.allSettled(players.value.map((p) => p.play()));
  if (results.some((r) => r.status === "rejected"))
    notify("部分素材无法播放，请分别检查素材", true);
}
function pause() {
  players.value.forEach((p) => p.pause());
}
async function choose(id: string) {
  if (await act((pid) => api.selectCandidate(pid, props.shotId, id)))
    closeDialog();
}
</script>
<template>
  <p class="muted">
    核对人物和服装、台词与口型、动作与衔接。分别试听原声后，再决定选用。
  </p>
  <template v-if="candidates.length >= 2"
    ><div class="actions comparison-controls">
      <button class="button secondary" @click="play">从头一起播放</button
      ><button class="button ghost" @click="pause">暂停两边</button
      ><label class="check-label"
        >试听声音
        <select v-model="sound">
          <option value="0">左边</option>
          <option value="1">右边</option>
          <option value="silent">全部静音</option>
        </select></label
      >
    </div>
    <div class="comparison-grid">
      <article
        v-for="(candidate, side) in selected"
        :key="side"
        class="comparison-card"
      >
        <template v-if="candidate"
          ><label class="label" :for="`compare-${side}`"
            >{{ side ? "右边" : "左边" }}候选</label
          ><select
            :id="`compare-${side}`"
            :value="pair[side]"
            @change="change(side, ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="c in candidates" :key="c.id" :value="c.id">
              V{{ shot.candidates.indexOf(c) + 1
              }}{{ shot.selected === c.id ? " · 已选用" : "" }}
            </option></select
          ><MediaPreview
            ref="players"
            :key="candidate.id"
            :candidate="candidate"
            :muted="String(side) !== sound"
          />
          <p class="hint">
            {{
              candidate.provider === "seedance"
                ? "AI 视频"
                : candidate.provider === "upload"
                  ? "导入素材"
                  : "文字预演"
            }}
            · 预估 {{ money(candidate.estimated_cost)
            }}{{
              candidate.edit
                ? ` · 剪辑 ${candidate.edit.start} 秒 → ${candidate.edit.end ?? "末尾"}`
                : ""
            }}
          </p>
          <p class="hint">
            字幕：{{ (candidate.subtitle_text ?? shot.narration) || "无台词" }}
          </p>
          <div class="actions">
            <button
              class="button"
              :disabled="locked"
              @click="choose(candidate.id)"
            >
              选用{{ side ? "右" : "左" }}边</button
            ><button
              class="button ghost"
              @click="
                openDialog({
                  kind: 'candidate',
                  shotId,
                  candidateId: candidate.id,
                })
              "
            >
              详情 / 剪辑 / 审核
            </button>
          </div></template
        >
      </article>
    </div>
    <p class="hint">
      对比播放完整原素材；已设置的剪辑区间显示在候选下方。一起播放用于人工比较，不保证逐帧同步。
    </p></template
  >
  <div v-else class="info">有效候选已变化，至少需要两个有效候选才能对比。</div>
</template>
