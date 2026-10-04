<script setup lang="ts">
import { reactive, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import type { ShotInput } from "../types";
const props = defineProps<{ id: string }>();
const { project, locked, act, api, closeDialog } = useStudio();
const s = project.value.shots.find((s) => s.id === props.id)!;
const form = reactive<ShotInput>({
  title: s.title,
  scene: s.scene,
  visual: s.visual,
  narration: s.narration,
  speaker: s.speaker,
  duration: s.duration,
  characters: [...s.characters],
  purpose: s.purpose || "",
  start_state: s.start_state || "",
  end_state: s.end_state || "",
  delivery: s.delivery || "",
  beat_index: s.beat_index || null,
});
const beatIndex = ref<string | number>(s.beat_index ?? "");
const fields = [
  { key: "purpose", label: "本镜头新增的信息 / 情绪", max: 300 },
  { key: "start_state", label: "开场状态：人物、位置、道具", max: 500 },
  { key: "end_state", label: "结束状态：下一镜如何接上", max: 500 },
] as const;
async function save() {
  if (
    await act((pid) =>
      api.shot(pid, props.id, {
        ...form,
        beat_index: beatIndex.value === "" ? null : Number(beatIndex.value),
      }),
    )
  )
    closeDialog();
}
</script>
<template>
  <form @submit.prevent="save">
    <div class="grid two">
      <div class="field">
        <label class="label" for="shot-title">镜头标题</label
        ><input
          id="shot-title"
          v-model="form.title"
          maxlength="100"
          required
          :disabled="locked"
        />
      </div>
      <div class="field">
        <label class="label" for="shot-scene">场景</label
        ><input
          id="shot-scene"
          v-model="form.scene"
          maxlength="200"
          required
          :disabled="locked"
        />
      </div>
    </div>
    <div class="field">
      <label class="label" for="visual">画面与动作</label
      ><textarea
        id="visual"
        v-model="form.visual"
        maxlength="2000"
        rows="4"
        required
        :disabled="locked"
      ></textarea>
    </div>
    <div v-for="field in fields" :key="field.key" class="field">
      <label class="label" :for="`shot-${field.key}`">{{ field.label }}</label
      ><textarea
        :id="`shot-${field.key}`"
        v-model="form[field.key]"
        :maxlength="field.max"
        rows="2"
        :disabled="locked"
      ></textarea>
    </div>
    <div class="field">
      <label class="label" for="beat-index"
        >来源剧本段落编号（对话 / 混合形式必填）</label
      ><input
        id="beat-index"
        v-model="beatIndex"
        type="number"
        min="1"
        max="24"
        :disabled="locked"
      />
    </div>
    <div class="field">
      <label class="label" for="delivery">台词表演：情绪、语气与停顿</label
      ><textarea
        id="delivery"
        v-model="form.delivery"
        maxlength="300"
        rows="2"
        :disabled="locked"
      ></textarea>
    </div>
    <div class="field">
      <label class="label" for="narration">对白 / 旁白</label
      ><textarea
        id="narration"
        v-model="form.narration"
        maxlength="300"
        rows="2"
        :disabled="locked"
      ></textarea>
    </div>
    <div class="grid two">
      <div class="field">
        <label class="label" for="speaker">说话人</label
        ><select id="speaker" v-model="form.speaker" :disabled="locked">
          <option
            v-for="name in [
              '',
              '旁白',
              ...project.characters.map((c) => c.name),
            ]"
            :key="name"
            :value="name"
          >
            {{ name || "无台词" }}
          </option>
        </select>
      </div>
      <div class="field">
        <label class="label" for="duration">计划时长（秒）</label
        ><input
          id="duration"
          v-model.number="form.duration"
          type="number"
          min="2"
          max="12"
          step="1"
          required
          :disabled="locked"
        />
      </div>
    </div>
    <label class="label">画面中出现的角色</label>
    <div class="actions">
      <label
        v-for="character in project.characters"
        :key="character.name"
        class="check-label"
        ><input
          v-model="form.characters"
          type="checkbox"
          :value="character.name"
          :disabled="locked"
        />{{ character.name }}</label
      >
    </div>
    <p class="hint">
      保存后需要重新审核此镜头。旧候选保留并过期，已上传音轨解除关联。
    </p>
    <div class="dialog-actions">
      <button class="button" :disabled="locked">保存分镜</button>
    </div>
  </form>
</template>
