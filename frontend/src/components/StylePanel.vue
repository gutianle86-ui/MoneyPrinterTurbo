<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import Badge from "./Badge.vue";
const { project, state, locked, act, api, showProject } = useStudio();
const recommendation = computed(() => project.value.style_recommendation);
</script>
<template>
  <section class="panel workflow-panel">
    <div class="panel-title">
      <h2>统一画风</h2>
      <Badge :tone="project.style ? 'green' : 'amber'">{{
        project.style ? "已确定 · 全项目使用" : "等待确认"
      }}</Badge>
    </div>
    <p v-if="project.style">{{ project.style }}</p>
    <p v-else class="muted">
      默认自动推荐：AI
      起草策划时会一起推荐画风，确认后再生成分镜。也可以直接选预设。
    </p>
    <div
      v-if="recommendation && project.style !== recommendation.style"
      class="brief-summary"
    >
      <strong>推荐：{{ recommendation.name }}</strong>
      <p>{{ recommendation.style }}</p>
      <p class="hint">推荐理由：{{ recommendation.reason }}</p>
      <button class="button" :disabled="locked" @click="act(api.acceptStyle)">
        采用推荐画风
      </button>
    </div>
    <div class="actions">
      <button
        class="button secondary"
        :disabled="locked"
        @click="showProject(true)"
      >
        选择预设 / 自定义</button
      ><button
        class="button ghost"
        :disabled="
          locked ||
          !state.status?.settings.llm_api_key_configured ||
          !state.status.settings.llm_model
        "
        @click="act(api.recommendStyle)"
      >
        {{ recommendation ? "重新推荐画风" : "单独推荐画风" }}（文本计费）
      </button>
    </div>
    <p class="hint">
      重新推荐只提供建议，采用后才会替换当前画风。可在项目设置中将画风保存为个人预设。项目内所有镜头继承确认的画风。
    </p>
  </section>
</template>
