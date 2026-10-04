<script setup lang="ts">
import { computed, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { isCurrentExport, picked } from "../domain";
import PageHeader from "../components/PageHeader.vue";
import NeedScript from "../components/NeedScript.vue";
import CostPanel from "../components/CostPanel.vue";
import ExportCard from "../components/ExportCard.vue";
import Badge from "../components/Badge.vue";
const {
  project,
  state,
  locked,
  canMake,
  selectedCount,
  activeScript,
  navigate,
  act,
  api,
} = useStudio();
const voice = ref(false);
const complete = computed(
  () => selectedCount.value === project.value.shots.length && canMake.value,
);
const nextStage = computed(() =>
  !project.value.script_approved
    ? 0
    : !project.value.characters_approved
      ? 1
      : project.value.shots.some((s) => !s.approved)
        ? 2
        : 3,
);
const nextLabel = computed(
  () => ["确认剧本", "确认角色", "审核分镜", "制作并选用镜头"][nextStage.value],
);
const previewCount = computed(
  () =>
    project.value.shots.filter((s) => picked(s)?.provider === "preview").length,
);
const miniOnly = computed(
  () =>
    project.value.shots.length > 0 &&
    project.value.shots.every((s) =>
      picked(s)?.request?.model?.startsWith("doubao-seedance-2-0-mini-"),
    ),
);
const entries = computed(() =>
  project.value.exports
    .filter((e) => e.kind !== "animatic")
    .slice()
    .reverse(),
);
const current = computed(() =>
  entries.value.filter((e) => isCurrentExport(project.value, e)),
);
const history = computed(() =>
  entries.value.filter((e) => !isCurrentExport(project.value, e)),
);
</script>
<template>
  <NeedScript v-if="!project.active_script" /><template v-else
    ><PageHeader
      title="把选定的镜头，连成一个故事"
      subtitle="按分镜顺序合成竖屏 MP4，同时保存字幕和制作清单。历史导出不会被覆盖。" />
    <div v-if="!complete" class="info">
      <strong>尚未开始合成</strong>
      <p>
        当前选用了 {{ selectedCount }} /
        {{ project.shots.length }} 个有效镜头。请先{{
          nextLabel
        }}，完成后才能合成。
      </p>
      <button class="button secondary small" @click="navigate(nextStage)">
        前往{{ nextLabel }} →
      </button>
    </div>
    <div class="info">
      剪辑入点 / 出点请在“镜头制作 →
      候选”中设置。默认保留完整素材；设置后按选定区间导出，原素材仍保留。裁掉对白后需核对字幕。
    </div>
    <div
      v-if="
        project.shots.some(
          (s) =>
            s.narration &&
            !s.audio &&
            picked(s)?.provider === 'seedance' &&
            !picked(s)?.dialogue_requested,
        )
      "
      class="info"
    >
      当前有旧镜头生成时未传入剧本台词。保留原声不会补回缺失的对白；请先试听，可导入配音音轨，或重新生成并检查对白。
    </div>
    <div class="panel">
      <div class="panel-title">
        <h2>{{ activeScript?.title }}</h2>
        <Badge :tone="complete ? 'green' : 'amber'">{{
          complete ? "可以导出" : "镜头尚未就绪"
        }}</Badge>
      </div>
      <div class="stats">
        <div class="stat">
          <span>选用镜头</span
          ><b
            >{{ selectedCount }}<small>/ {{ project.shots.length }}</small></b
          >
        </div>
        <div class="stat">
          <span>文字预演卡</span><b>{{ previewCount }}<small>个</small></b>
        </div>
        <div class="stat">
          <span>输出规格</span
          ><b
            >9:16<small
              >正式 {{ miniOnly ? "720p" : "1080p" }} / 预演 540p</small
            ></b
          >
        </div>
      </div>
      <label class="check-label"
        ><input
          v-model="voice"
          type="checkbox"
          :disabled="locked || !state.status?.local_voice"
        />使用系统朗读试听（会覆盖原声，仅用于预演）</label
      >
      <p class="hint">
        默认保留视频原声；上传音轨会替换该镜头的原声。勾选系统朗读后，有台词且未上传音轨的镜头会改用本机朗读。合成只在本机剪辑、添加字幕和音轨，不会调用
        Seedance，也不会自动补配对白。正式导出为
        {{ miniOnly ? "720 × 1280" : "1080 × 1920" }}，预演为 540 × 960。
      </p>
      <div class="actions" style="margin-top: 24px">
        <button
          class="button"
          :disabled="locked || !complete"
          @click="act((pid) => api.export(pid, 'preview', voice))"
        >
          {{ locked ? "任务处理中…" : "合成预演 MP4" }}</button
        ><button
          class="button secondary"
          :disabled="locked || !complete || previewCount > 0"
          @click="act((pid) => api.export(pid, 'production', voice))"
        >
          {{ locked ? "任务处理中…" : "合成正式 MP4" }}
        </button>
      </div>
      <p v-if="previewCount" class="hint">
        正式导出需要把全部文字预演卡替换为导入画面或 AI 视频。
      </p>
    </div>
    <CostPanel />
    <div class="panel-title">
      <h2>本次合成结果</h2>
      <span class="muted">{{ current.length }} 个版本</span>
    </div>
    <ExportCard v-for="entry in current" :key="entry.id" :entry="entry" />
    <div v-if="!current.length" class="empty">
      当前选用的镜头还没有合成结果。完成镜头制作并合成后，视频会显示在这里。
    </div>
    <details v-if="history.length" class="export-history">
      <summary>历史导出（{{ history.length }}）</summary>
      <p class="hint">
        这里保留旧版本和早期记录，包括之前的示例预演；这些不是当前选用镜头的合成结果。
      </p>
      <ExportCard
        v-for="entry in history"
        :key="entry.id"
        :entry="entry"
        historical
      /></details
  ></template>
</template>
