<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import Badge from "./Badge.vue";
const { project } = useStudio();
const workflow = computed(() => project.value.workflow_status);
</script>
<template>
  <div v-if="!workflow.enabled" class="info">
    旧项目沿用原流程。可在故事页填写内容策划，启用“预演 → 样片 → 批量”检查。
  </div>
  <section v-else class="panel workflow-panel">
    <div class="panel-title">
      <h2>制作前检查</h2>
      <Badge :tone="workflow.pilot_ok ? 'green' : 'amber'">{{
        workflow.pilot_ok ? "样片已审核，可分批制作" : "先验证，再花钱"
      }}</Badge>
    </div>
    <div class="actions">
      <Badge :tone="workflow.content_ok ? 'green' : 'amber'">{{
        workflow.content_ok ? "剧本 ✓" : "剧本待审"
      }}</Badge
      ><Badge :tone="workflow.preview_ok ? 'green' : 'amber'">{{
        workflow.preview_ok ? "预演 ✓" : "预演待审"
      }}</Badge
      ><Badge :tone="workflow.pilot_ok ? 'green' : 'amber'">{{
        workflow.pilot_ok ? "样片 ✓" : "只试一个镜头"
      }}</Badge>
    </div>
    <ul v-if="workflow.blockers.length" class="workflow-list">
      <li v-for="item in workflow.blockers" :key="item">{{ item }}</li>
    </ul>
    <p v-else class="hint">
      策划与预演已通过。样片未通过前，请只选一个关键镜头、一个候选；在候选窗口观看后记录样片审核。
    </p>
    <details v-if="workflow.warnings.length">
      <summary>节奏与衔接提示（{{ workflow.warnings.length }}）</summary>
      <ul class="workflow-list">
        <li v-for="item in workflow.warnings" :key="item">{{ item }}</li>
      </ul>
    </details>
    <p class="hint">
      通过检查不代表画面质量或推广效果达标。修改内容、角色或分镜后，相关审核须重做。
    </p>
  </section>
</template>
