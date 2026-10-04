<script setup lang="ts">
import { computed, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import Badge from "./Badge.vue";
const { project, state, locked, canMake, asset, openDialog, act, api } =
  useStudio();
const voice = ref(Boolean(state.status?.local_voice));
const entries = computed(() =>
  project.value.exports.filter((e) => e.kind === "animatic"),
);
const latest = computed(() =>
  [...entries.value]
    .reverse()
    .find(
      (e) => e.story_revision === project.value.workflow_status.story_revision,
    ),
);
const spoken = computed(() =>
  latest.value?.audio_sources?.some((a) => a.source !== "silent"),
);
</script>
<template>
  <section class="panel workflow-panel">
    <div class="panel-title">
      <h2>免费预演：先检查整条节奏</h2>
      <Badge :tone="project.workflow_status.preview_ok ? 'green' : 'amber'">{{
        project.workflow_status.preview_ok ? "当前预演已审核" : "付费前完成"
      }}</Badge>
    </div>
    <p class="muted">
      用文字分镜卡串起完整故事，不需要先生成角色视频。检查开头、看点出现的时间、结尾和镜头顺序。
    </p>
    <label class="check-label"
      ><input
        v-model="voice"
        type="checkbox"
        :disabled="locked || !state.status?.local_voice"
      />使用本机朗读试听（免费）</label
    >
    <p class="hint">
      这不是人物画面效果预览。{{
        state.status?.local_voice
          ? "系统朗读只用于检查节奏，不代表最终表演或口型。"
          : "此设备无系统朗读，无音轨时预演为静音，需自行朗读检查。"
      }}预演不会覆盖现有素材或选用结果。
    </p>
    <div class="actions">
      <button
        class="button secondary"
        :disabled="locked || !canMake"
        @click="act((pid) => api.export(pid, 'animatic', voice))"
      >
        生成完整免费预演</button
      ><button
        v-if="latest"
        class="button"
        :disabled="locked"
        @click="
          openDialog({
            kind: 'review',
            stage: 'preview',
            artifactId: latest.id,
          })
        "
      >
        已观看，记录审核
      </button>
    </div>
    <div v-if="latest" class="animatic-result">
      <video
        :key="latest.file"
        :src="asset(latest.file)"
        controls
        playsinline
        preload="metadata"
      ></video>
      <div>
        <strong>当前分镜预演 · {{ latest.duration.toFixed(1) }} 秒</strong>
        <p class="hint">
          {{ spoken ? "含试听音轨" : "静音预演，请自行朗读检查"
          }}<br />前几秒是否交代了核心冲突？看点是否兑现？结尾是否留下具体问题？
        </p>
      </div>
    </div>
    <p v-else-if="entries.length" class="hint">
      已有预演属于旧版本，修改分镜后请重新生成。
    </p>
  </section>
</template>
