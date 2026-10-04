<script setup lang="ts">
import { computed } from "vue";
import { useStudio } from "../composables/useStudio";
import { dateText, money } from "../domain";
import type { ExportRecord } from "../types";
import Badge from "./Badge.vue";
const props = defineProps<{ entry: ExportRecord; historical?: boolean }>();
const { project, locked, asset, openDialog } = useStudio();
const type = computed(() =>
  props.entry.kind === "preview" ? "分镜预演" : "正式合成",
);
const sources: Record<string, string> = {
  uploaded: "上传音轨",
  system_speech: "系统朗读（试听）",
  native: "视频原声",
  silent: "无声",
};
const audio = computed(
  () =>
    [
      ...new Set(
        (props.entry.audio_sources || []).map(
          (a) => sources[a.source] || "未知",
        ),
      ),
    ].join("、") || "旧记录未记录，请播放确认",
);
const metrics = computed(() => {
  const f = props.entry.feedback;
  if (!f) return [];
  const values = [];
  for (const [key, label] of [
    ["views", "播放"],
    ["likes", "点赞"],
    ["conversions", "转化"],
  ] as const)
    if (f[key] != null)
      values.push(`${label} ${f[key]!.toLocaleString("zh-CN")}`);
  if (f.revenue != null) values.push(`收入 ${money(f.revenue)}`);
  if (f.actual_cost != null) values.push(`实际总成本 ${money(f.actual_cost)}`);
  if (f.revenue != null && f.actual_cost != null) {
    const profit = f.revenue - f.actual_cost;
    values.push(`利润 ${money(profit)}`);
    if (f.actual_cost > 0)
      values.push(`成本回报率 ${((profit / f.actual_cost) * 100).toFixed(1)}%`);
  }
  return values;
});
</script>
<template>
  <article class="export-card">
    <video
      :src="asset(entry.file)"
      controls
      playsinline
      :preload="historical ? 'none' : 'metadata'"
    ></video>
    <div>
      <div class="card-head">
        <h2>{{ historical ? "历史" : "本次" }}{{ type }}</h2>
        <Badge :tone="entry.kind === 'preview' ? 'amber' : 'green'">{{
          type
        }}</Badge>
      </div>
      <p>
        {{ dateText(entry.created_at) }}<br />{{ entry.duration.toFixed(1) }} 秒
        · {{ entry.resolution ? entry.resolution + " · " : "" }}MP4 / H.264<br />声音：{{
          audio
        }}
      </p>
      <template v-if="entry.kind === 'production'"
        ><p v-if="entry.cost_summary" class="hint">
          导出时项目累计预估
          {{ money(entry.cost_summary.estimated_video_cost) }} · 选用素材预估
          {{ money(entry.cost_summary.selected_cost) }}
        </p>
        <p v-else class="hint">此旧版本没有导出时的成本快照。</p>
        <template v-if="entry.feedback"
          ><p>
            {{ entry.feedback.platform || "已记录发布效果" }}<br />{{
              metrics.join(" · ")
            }}
          </p>
          <a
            v-if="/^https?:\/\//.test(entry.feedback.published_url)"
            class="text-button"
            :href="entry.feedback.published_url"
            target="_blank"
            rel="noopener noreferrer"
            >打开发布链接 ↗</a
          >
          <p v-if="entry.feedback.notes" class="hint feedback-notes">
            {{ entry.feedback.notes }}
          </p></template
        >
        <div class="actions">
          <button
            class="button ghost small"
            :disabled="locked"
            @click="openDialog({ kind: 'feedback', id: entry.id })"
          >
            {{ entry.feedback ? "更新发布效果" : "记录发布效果与实际成本" }}
          </button>
        </div></template
      >
      <div class="actions">
        <a
          class="button"
          :href="asset(entry.file)"
          :download="`${project.title}-${entry.id}.mp4`"
          >下载视频 ↓</a
        ><a class="button secondary" :href="asset(entry.subtitle)" download
          >字幕 SRT</a
        ><a class="button ghost" :href="asset(entry.manifest)" download
          >制作清单</a
        >
      </div>
    </div>
  </article>
</template>
