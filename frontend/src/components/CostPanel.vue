<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import { money } from "../domain";
const { project } = useStudio();
const cost = computed(() => project.value.cost_summary);
</script>
<template>
  <section v-if="cost" class="panel cost-panel">
    <div class="panel-title">
      <h2>制作成本复盘</h2>
      <span class="muted">视频费用预估</span>
    </div>
    <div class="stats">
      <div class="stat">
        <span>项目累计预估</span><b>{{ money(cost.estimated_video_cost) }}</b>
      </div>
      <div class="stat">
        <span>当前选用素材预估</span><b>{{ money(cost.selected_cost) }}</b>
      </div>
      <div class="stat">
        <span>其余生成预估</span><b>{{ money(cost.unselected_cost) }}</b>
      </div>
      <div class="stat">
        <span>多次制作的镜头</span
        ><b>{{ cost.multiple_candidate_shots }}<small>个</small></b>
      </div>
    </div>
    <p class="hint">
      累计包含旧剧本版本。其余生成包括备用、淘汰、过期和待核对候选，不等于浪费或实际账单。文本服务、配音和人工成本未计入；{{
        cost.unsettled_tasks
          ? `${cost.unsettled_tasks} 个任务结果仍待核对，预估暂时保留。`
          : "实际费用请以服务商账单为准。"
      }}
    </p>
    <details>
      <summary>逐镜头明细 · {{ cost.paid_attempts }} 条 AI 制作记录</summary>
      <div class="table-wrap">
        <table class="shot-table">
          <thead>
            <tr>
              <th>镜头</th>
              <th>AI 制作记录</th>
              <th>累计预估</th>
              <th>选用素材预估</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(shot, index) in cost.shots" :key="shot.shot_id">
              <td>{{ index + 1 }}. {{ shot.title }}</td>
              <td>{{ shot.attempts }}</td>
              <td>{{ money(shot.estimated_cost) }}</td>
              <td>{{ money(shot.selected_cost) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </section>
</template>
