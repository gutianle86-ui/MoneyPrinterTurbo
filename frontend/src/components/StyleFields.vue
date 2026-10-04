<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useStudio } from "../composables/useStudio";
import type { ProjectInput } from "../types";
const model = defineModel<ProjectInput>({ required: true });
const { state, locked, guarded, api, notify } = useStudio();
const choice = ref(
  model.value.style_mode === "preset"
    ? model.value.style_preset_id
    : model.value.style_mode,
);
const name = ref(""),
  originalAuto = model.value.style_mode === "auto" ? model.value.style : "",
  custom = ref(model.value.style);
const presets = computed(() => state.status?.style_presets || []);
watch(choice, (value, previous) => {
  if (previous === "custom") custom.value = model.value.style;
  const preset = presets.value.find((p) => p.id === value);
  if (value === "auto") model.value.style = originalAuto;
  else if (preset) {
    model.value.style = preset.style;
    custom.value = preset.style;
  } else model.value.style = custom.value;
  model.value.style_mode =
    value === "auto" || value === "custom" ? value : "preset";
  model.value.style_preset_id =
    model.value.style_mode === "preset" ? value : "";
});
async function save() {
  if (!name.value.trim()) return notify("请先给个人预设起一个名称", true);
  if (
    await guarded(async () => {
      await api.saveStylePreset({
        name: name.value.trim(),
        style: model.value.style.trim(),
      });
      state.status!.style_presets = await api.stylePresets();
    })
  ) {
    name.value = "";
    notify("个人画风预设已保存，以后创建项目可直接选择");
  }
}
</script>
<template>
  <div class="field">
    <label class="label" for="style-choice">统一画风</label
    ><select id="style-choice" v-model="choice" :disabled="locked">
      <option value="auto">自动推荐（默认）</option>
      <optgroup label="题材预设">
        <option
          v-for="p in presets.filter((p) => !p.personal)"
          :key="p.id"
          :value="p.id"
        >
          {{ p.name }}
        </option>
      </optgroup>
      <optgroup label="我的预设">
        <option
          v-for="p in presets.filter((p) => p.personal)"
          :key="p.id"
          :value="p.id"
        >
          {{ p.name }}
        </option>
      </optgroup>
      <option value="custom">自定义画风</option>
    </select>
    <p class="hint">
      {{
        choice === "auto"
          ? originalAuto
            ? "保留已确认的画风；可在故事页重新推荐。"
            : "先创建项目，AI 起草策划时一起推荐，确认后用于分镜。"
          : "项目内所有镜头继承此画风；选择自定义可调整描述。"
      }}
    </p>
    <label class="label" for="style">画风描述</label
    ><textarea
      id="style"
      v-model="model.style"
      rows="3"
      maxlength="500"
      :readonly="choice !== 'custom'"
      :required="choice === 'custom'"
      :disabled="locked"
      :placeholder="
        choice === 'auto'
          ? '创建后由 AI 分析原文并推荐，无需填写'
          : '填写线条、色彩、光影等视觉风格'
      "
    ></textarea>
  </div>
  <div v-if="model.style.trim()" class="field">
    <label class="label" for="style-preset-name">保存为个人预设（可选）</label>
    <div class="actions">
      <input
        id="style-preset-name"
        v-model="name"
        maxlength="40"
        placeholder="例如：我的都市甜宠画风"
        :disabled="locked"
      /><button
        type="button"
        class="button secondary"
        :disabled="locked"
        @click="save"
      >
        保存预设
      </button>
    </div>
  </div>
</template>
