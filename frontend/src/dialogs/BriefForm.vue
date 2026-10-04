<script setup lang="ts">
import { computed, reactive } from "vue";
import { useStudio } from "../composables/useStudio";
import { briefFields, projectFormat } from "../domain";
import type { ContentBrief, DramaBeat } from "../types";
const { project, locked, act, api, notify, closeDialog } = useStudio();
const format = projectFormat(project.value);
const form = reactive<ContentBrief>({
  format,
  audience: "",
  source_notes: "",
  promise: "",
  opening: "",
  payoff: "",
  cliffhanger: "",
  narration: "",
  target_duration: 30,
  beats: [],
  ...JSON.parse(JSON.stringify(project.value.workflow?.brief || {})),
});
form.format = format;
const fields = computed(() =>
  briefFields.filter((f) => format === "narration" || f.key !== "narration"),
);
const beatFields = [
  { key: "scene", label: "场景", max: 200 },
  { key: "action", label: "动作与反应", max: 1000 },
  { key: "speaker", label: "说话人（无台词可留空）", max: 40 },
  { key: "line", label: "台词（无声段落留空）", max: 300 },
  { key: "emotion", label: "情绪、语气与停顿", max: 300 },
] as const;
function add() {
  if (form.beats.length >= 24) return notify("最多24段剧本", true);
  form.beats.push({
    scene: "",
    action: "",
    speaker: "",
    line: "",
    emotion: "",
  } as DramaBeat);
}
if (format !== "narration" && !form.beats.length) add();
async function save() {
  const data = {
    ...form,
    narration: format === "narration" ? form.narration : "",
    beats: format === "narration" ? [] : form.beats,
  };
  if (await act((pid) => api.brief(pid, data))) closeDialog();
}
</script>
<template>
  <form @submit.prevent="save">
    <div v-for="field in fields" :key="field.key" class="field">
      <label class="label" :for="`brief-${field.key}`">{{ field.label }}</label
      ><textarea
        :id="`brief-${field.key}`"
        v-model="form[field.key]"
        :rows="field.key === 'narration' ? 6 : 2"
        :maxlength="field.max"
        required
        :disabled="locked"
      ></textarea>
    </div>
    <template v-if="format !== 'narration'"
      ><h3>完整表演剧本</h3>
      <p class="hint">
        按故事顺序填写。每段一个说话人；动作或反应段可不填台词。
      </p>
      <fieldset
        v-for="(beat, index) in form.beats"
        :key="index"
        class="drama-beat"
      >
        <legend>剧本段落 {{ index + 1 }}</legend>
        <label v-for="field in beatFields" :key="field.key" class="label"
          >{{ field.label
          }}<textarea
            v-model="beat[field.key]"
            :maxlength="field.max"
            :rows="field.key === 'action' ? 2 : 1"
            :required="['scene', 'action'].includes(field.key)"
            :disabled="locked"
          ></textarea></label
        ><button
          type="button"
          class="button ghost small"
          :disabled="locked"
          @click="form.beats.splice(index, 1)"
        >
          删除这一段
        </button>
      </fieldset>
      <button
        type="button"
        class="button secondary"
        :disabled="locked"
        @click="add"
      >
        添加剧本段落
      </button></template
    >
    <div class="field">
      <label class="label" for="brief-duration">目标时长（秒）</label
      ><input
        id="brief-duration"
        v-model.number="form.target_duration"
        type="number"
        min="15"
        max="120"
        required
        :disabled="locked"
      />
    </div>
    <p class="hint">修改后需重新审核；已有视频保留。</p>
    <div class="dialog-actions">
      <button class="button" :disabled="locked">保存策划</button>
    </div>
  </form>
</template>
