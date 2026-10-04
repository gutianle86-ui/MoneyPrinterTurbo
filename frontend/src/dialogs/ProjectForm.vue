<script setup lang="ts">
import { ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { formatLabels, projectFormat } from "../domain";
import type { ProjectInput } from "../types";
import StyleFields from "../components/StyleFields.vue";
const props = defineProps<{ edit?: boolean }>();
const {
  state,
  project,
  locked,
  act,
  guarded,
  api,
  openProject,
  navigate,
  reloadProjects,
  closeDialog,
} = useStudio();
const p = project.value;
const form = ref<ProjectInput>(
  props.edit
    ? {
        title: p.title,
        premise: p.premise,
        story_format: projectFormat(p),
        style: p.style,
        style_mode: p.style_mode || "custom",
        style_preset_id: p.style_preset_id || "",
        budget: p.budget,
      }
    : {
        title: "我的第一部漫剧",
        premise: "",
        story_format: "dialogue",
        style: "",
        style_mode: "auto",
        style_preset_id: "",
        budget: 100,
      },
);
async function save() {
  const data = { ...form.value, style: form.value.style.trim() };
  const ok = props.edit
    ? await act((pid) => api.updateProject(pid, data), 0)
    : await guarded(async () => {
        const result = await api.createProject(data);
        await openProject(result.id);
        navigate(0);
      });
  if (ok) {
    closeDialog();
    await reloadProjects();
    state.batchShots.clear();
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <div class="field">
      <label class="label" for="project-title">项目名称</label
      ><input
        id="project-title"
        v-model="form.title"
        required
        maxlength="100"
        :disabled="locked"
      />
    </div>
    <div class="field">
      <label class="label" for="premise">原文片段 / 准确梗概</label
      ><textarea
        id="premise"
        v-model="form.premise"
        required
        maxlength="5000"
        rows="4"
        :disabled="locked"
        placeholder="粘贴关键原文，注明章节和事实；不要只填书名。"
      ></textarea>
    </div>
    <div class="field">
      <label class="label" for="story-format">制作形式</label
      ><select id="story-format" v-model="form.story_format" :disabled="locked">
        <option
          v-for="(label, value) in formatLabels"
          :key="value"
          :value="value"
        >
          {{ label }}
        </option>
      </select>
      <p class="hint">
        对话短剧由角色对话与动作推进；旁白推文由讲述者串联；混合形式允许少量旁白。切换后需重新策划和审核。
      </p>
    </div>
    <StyleFields v-model="form" />
    <p v-if="edit && project.shots.length" class="hint">
      更换画风后，需要重新审核角色与分镜，并重做预演；旧素材保留。
    </p>
    <div class="field">
      <label class="label" for="budget"
        >视频生成预算上限（元，按预估控制）</label
      ><input
        id="budget"
        v-model.number="form.budget"
        type="number"
        min="1"
        max="100000"
        step="0.01"
        required
        :disabled="locked"
      />
    </div>
    <div class="dialog-actions">
      <button
        type="button"
        class="button ghost"
        :disabled="state.requestPending"
        @click="closeDialog"
      >
        取消</button
      ><button class="button" :disabled="locked">
        {{ edit ? "保存项目" : "创建项目" }}
      </button>
    </div>
  </form>
</template>
