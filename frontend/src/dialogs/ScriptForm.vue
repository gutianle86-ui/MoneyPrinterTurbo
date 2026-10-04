<script setup lang="ts">
import { ref } from "vue";
import { useStudio } from "../composables/useStudio";
import type { Script } from "../types";
const props = defineProps<{ id?: string }>();
const { project, locked, act, api, failure, closeDialog } = useStudio();
const sample = {
  title: "新剧本",
  hook: "一句话冲突",
  synopsis: "故事梗概",
  characters: [
    { name: "主角", appearance: "角色外观和服装", voice: "Tingting" },
  ],
  shots: [
    {
      title: "开场",
      scene: "室内",
      visual: "主角推开房门，镜头缓慢推近",
      narration: "门后的人，竟然是我自己。",
      speaker: "旁白",
      duration: 6,
      characters: ["主角"],
      purpose: "呈现开头的异常",
      start_state: "主角站在门外，右手握门把",
      end_state: "主角推开房门，停在门口",
    },
  ],
};
const text = ref(
  JSON.stringify(
    project.value.scripts.find((s) => s.id === props.id)?.script || sample,
    null,
    2,
  ),
);
async function save() {
  try {
    const data = JSON.parse(text.value) as Script;
    if (await act((pid) => api.importScript(pid, data))) closeDialog();
  } catch (error) {
    failure(error);
  }
}
</script>
<template>
  <p class="hint">
    保存后新增一个候选方案，原剧本和已有镜头不会被覆盖。采用 JSON
    格式，角色名称应与镜头引用一致。
  </p>
  <form @submit.prevent="save">
    <label class="label" for="script-json">剧本内容</label
    ><textarea
      id="script-json"
      v-model="text"
      class="code"
      rows="16"
      required
      :disabled="locked"
    ></textarea>
    <div class="dialog-actions">
      <button class="button" :disabled="locked">保存为新方案</button>
    </div>
  </form>
</template>
