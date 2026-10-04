<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import { formatLabels, hasBrief, projectFormat } from "../domain";
import Badge from "./Badge.vue";
const { project, state, locked, openDialog, showProject, act, api } =
  useStudio();
const format = computed(() => projectFormat(project.value));
const brief = computed(() => project.value.workflow?.brief);
const mismatch = computed(
  () =>
    hasBrief(project.value) &&
    (brief.value?.format || "narration") !== format.value,
);
</script>
<template>
  <section class="panel workflow-panel">
    <div class="panel-title">
      <h2>先确认剧本，再制作画面</h2>
      <Badge :tone="project.workflow_status.content_ok ? 'green' : 'amber'">{{
        project.workflow_status.content_ok ? "剧本已审核" : "待策划"
      }}</Badge>
    </div>
    <div class="actions">
      <Badge>{{ formatLabels[format] }}</Badge
      ><button
        class="button ghost small"
        :disabled="locked"
        @click="showProject(true)"
      >
        更改制作形式
      </button>
    </div>
    <p class="muted">
      {{
        format === "narration"
          ? "原文分析 → 旁白文案 → 分镜预演"
          : "原文分析 → 场景、动作与角色台词 → 表演分镜与预演"
      }}
      → 单镜样片 → 批量制作。
    </p>
    <div v-if="mismatch" class="info">
      当前选择{{ formatLabels[format] }}，下方保留的是{{
        formatLabels[brief?.format || "narration"]
      }}草稿。请重新起草或编辑剧本，旧旁白不会自动变成角色对白。
    </div>
    <div v-if="hasBrief(project) && brief" class="brief-summary">
      <p><strong>给谁看：</strong>{{ brief.audience }}</p>
      <p><strong>核心反差：</strong>{{ brief.promise }}</p>
      <p v-if="brief.format === 'narration'" class="narration-copy">
        {{ brief.narration }}
      </p>
      <template v-else
        ><article
          v-for="(beat, index) in brief.beats"
          :key="index"
          class="drama-beat"
        >
          <strong>{{ index + 1 }}. {{ beat.scene }}</strong>
          <p class="muted">{{ beat.action }}</p>
          <p v-if="beat.line">
            <strong>{{ beat.speaker }}：</strong>{{ beat.line }}
          </p>
          <p v-else class="hint">无台词，保留动作与反应</p>
          <p v-if="beat.emotion" class="hint">表演：{{ beat.emotion }}</p>
        </article></template
      >
      <p class="hint">
        目标 {{ brief.target_duration }} 秒 · 本条兑现：{{ brief.payoff
        }}<br />结尾悬念：{{ brief.cliffhanger }}
      </p>
    </div>
    <p v-else class="hint">
      先在项目设置填写原文片段或准确梗概，再起草{{ formatLabels[format] }}。
    </p>
    <div class="actions">
      <button
        class="button secondary"
        :disabled="locked"
        @click="openDialog({ kind: 'brief' })"
      >
        {{ hasBrief(project) ? "修改内容策划" : "填写内容策划" }}</button
      ><button
        class="button ghost"
        :disabled="
          locked ||
          !state.status?.settings.llm_api_key_configured ||
          !state.status.settings.llm_model
        "
        @click="act(api.draftBrief)"
      >
        AI 起草策划（文本计费）</button
      ><button
        class="button"
        :disabled="locked || !hasBrief(project) || mismatch"
        @click="openDialog({ kind: 'review', stage: 'content' })"
      >
        核对剧本并记录审核
      </button>
    </div>
    <p class="hint">
      AI
      起草会替换策划草稿并撤销旧审核，不会生成视频。对话剧本按段保存动作、说话人和台词，审核后才进入分镜。
    </p>
  </section>
</template>
