<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { dateText } from "../domain";
import Badge from "./Badge.vue";
const { project } = useStudio();
const job = computed(() => project.value.job);
const clock = ref(Date.now());
const timer = setInterval(() => {
  clock.value = Date.now();
}, 1000);
onBeforeUnmount(() => clearInterval(timer));
const elapsed = computed(() =>
  job.value.started_at
    ? Math.max(
        0,
        Math.floor((clock.value - Date.parse(job.value.started_at)) / 1000),
      )
    : 0,
);
const history = computed(
  () =>
    ({
      done: "上次任务已完成",
      failed: "上次任务失败",
      interrupted: "上次任务已中断",
    })[job.value.status || ""] || "上次任务已结束",
);
</script>
<template>
  <div
    id="job-panel"
    class="job"
    :class="job.status === 'running' ? 'running' : 'idle history'"
    role="status"
    aria-live="polite"
  >
    <template v-if="job.status === 'running'"
      ><div class="job-top">
        <span>◌ 当前任务：{{ job.message }}</span
        ><span>{{ job.progress || 0 }}%</span>
      </div>
      <progress max="100" :value="job.progress || 0"></progress>
      <p class="hint">
        任务进行中 · 已等待 {{ Math.floor(elapsed / 60) }}分{{
          elapsed % 60
        }}秒。完成后会自动刷新，请勿重复提交。
      </p></template
    >
    <template v-else
      ><div class="job-top">
        <strong>当前没有运行中的任务</strong><Badge>空闲</Badge>
      </div>
      <p v-if="!job.status" class="hint">尚未提交制作任务。</p>
      <template v-else
        ><p v-if="job.status === 'done'">
          旧记录可在合成页的“历史导出”中查看。
        </p>
        <p v-else>
          <strong>{{ history }}：</strong>{{ job.message || "没有错误详情" }}
        </p>
        <p class="hint">
          结束于
          {{
            job.finished_at ? dateText(job.finished_at) : "时间未知"
          }}。以上是历史结果，不表示系统仍在处理或持续报错。
        </p></template
      ></template
    >
  </div>
</template>
