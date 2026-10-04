<script setup lang="ts">
import { reactive } from "vue";
import { useStudio } from "../composables/useStudio";
import { dateText } from "../domain";
import type { PublicationFeedback } from "../types";
const props = defineProps<{ id: string }>();
const { project, locked, act, api, notify, closeDialog } = useStudio();
const entry = project.value.exports.find((e) => e.id === props.id)!;
const form = reactive({
  ...entry.feedback,
  platform: entry.feedback?.platform || "",
  published_url: entry.feedback?.published_url || "",
  notes: entry.feedback?.notes || "",
  views: entry.feedback?.views ?? "",
  likes: entry.feedback?.likes ?? "",
  conversions: entry.feedback?.conversions ?? "",
  revenue: entry.feedback?.revenue ?? "",
  actual_cost: entry.feedback?.actual_cost ?? "",
});
const fields = [
  { key: "views", label: "播放量", financial: false },
  { key: "likes", label: "点赞量", financial: false },
  { key: "conversions", label: "转化数量", financial: false },
  { key: "revenue", label: "累计收入（元）", financial: true },
  {
    key: "actual_cost",
    label: "分摊到此版本的实际总成本（元）",
    financial: true,
  },
] as const;
async function save() {
  const data: PublicationFeedback = {
    platform: form.platform,
    published_url: form.published_url,
    notes: form.notes,
    views: null,
    likes: null,
    conversions: null,
    revenue: null,
    actual_cost: null,
  };
  for (const field of fields)
    data[field.key] = form[field.key] === "" ? null : Number(form[field.key]);
  if (await act((pid) => api.feedback(pid, props.id, data))) {
    closeDialog();
    notify("发布效果已保存到此导出版本");
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <p class="muted">
      记录版本：{{ dateText(entry.created_at) }} ·
      {{ entry.duration.toFixed(1) }} 秒。数据手动填写，可随时更新。
    </p>
    <div class="field">
      <label class="label" for="feedback-platform">发布平台</label
      ><input
        id="feedback-platform"
        v-model="form.platform"
        maxlength="80"
        :disabled="locked"
        placeholder="例如抖音 / 视频号"
      />
    </div>
    <div class="field">
      <label class="label" for="feedback-url">发布链接</label
      ><input
        id="feedback-url"
        v-model="form.published_url"
        type="url"
        maxlength="2000"
        :disabled="locked"
      />
    </div>
    <div class="grid two">
      <div v-for="field in fields" :key="field.key" class="field">
        <label class="label" :for="`feedback-${field.key}`">{{
          field.label
        }}</label
        ><input
          :id="`feedback-${field.key}`"
          v-model="form[field.key]"
          type="number"
          min="0"
          :max="field.financial ? 1e9 : 1e12"
          :step="field.financial ? '0.01' : '1'"
          :disabled="locked"
        />
      </div>
    </div>
    <p class="hint">
      未知数据留空；0
      表示确认没有。实际总成本可包含视频、文本、配音和人工。多个版本共用素材时请自行分摊成本。填写收入和实际成本后才显示利润。
    </p>
    <div class="field">
      <label class="label" for="feedback-notes">复盘笔记</label
      ><textarea
        id="feedback-notes"
        v-model="form.notes"
        rows="3"
        maxlength="2000"
        :disabled="locked"
        placeholder="开头、题材、返工原因，以及下条要调整的地方"
      ></textarea>
    </div>
    <div class="dialog-actions">
      <button class="button" :disabled="locked">保存复盘记录</button>
    </div>
  </form>
</template>
