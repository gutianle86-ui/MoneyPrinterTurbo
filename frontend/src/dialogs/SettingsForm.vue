<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { modelProfile } from "../domain";
const { state, locked, settingsInput, guarded, api, notify, closeDialog } =
  useStudio();
const form = reactive(settingsInput());
form.seedance_estimates = {
  ...form.seedance_estimates,
  [form.seedance_model]: form.estimate_per_second,
};
const preset = ref(
  state.status!.video_models[form.seedance_model]
    ? form.seedance_model
    : "custom",
);
const previousModel = ref(form.seedance_model);
const profile = computed(() => modelProfile(state.status, form.seedance_model));
function remember() {
  form.seedance_estimates[previousModel.value] = form.estimate_per_second;
}
function select() {
  remember();
  if (preset.value !== "custom") {
    form.seedance_model = preset.value;
    previousModel.value = preset.value;
    form.estimate_per_second =
      form.seedance_estimates[preset.value] ??
      state.status!.video_models[preset.value].default_estimate;
  }
}
function customChanged() {
  remember();
  previousModel.value = form.seedance_model;
  form.estimate_per_second = form.seedance_estimates[form.seedance_model] ?? 0;
}
async function save() {
  remember();
  if (
    await guarded(async () => {
      await api.settings(form);
      state.status = await api.status();
    })
  ) {
    closeDialog();
    notify("服务设置已保存");
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <div class="info">
      密钥只保存在本机配置文件，不会写入剧本或导出清单。留空保留已有密钥。
    </div>
    <h3>文本模型 · OpenAI 兼容接口</h3>
    <div class="field">
      <label class="label" for="llm-base">服务地址</label
      ><input
        id="llm-base"
        v-model="form.llm_base_url"
        type="url"
        required
        :disabled="locked"
      />
    </div>
    <div class="grid two">
      <div class="field">
        <label class="label" for="llm-model">模型名称</label
        ><input
          id="llm-model"
          v-model="form.llm_model"
          placeholder="填写服务商提供的模型 ID"
          :disabled="locked"
        />
      </div>
      <div class="field">
        <label class="label" for="llm-key">API Key</label
        ><input
          id="llm-key"
          v-model="form.llm_api_key"
          type="password"
          autocomplete="new-password"
          :disabled="locked"
          :placeholder="
            state.status?.settings.llm_api_key_configured
              ? '已配置，留空保留'
              : '尚未配置'
          "
        />
      </div>
    </div>
    <div class="field">
      <label class="label" for="llm-proxy">文本连接方式</label
      ><select
        id="llm-proxy"
        v-model="form.llm_use_env_proxy"
        :disabled="locked"
      >
        <option :value="true">使用环境代理（未配置时直连）</option>
        <option :value="false">直连（不使用环境代理）</option>
      </select>
      <p class="hint">仅影响文本策划、画风推荐和分镜生成。</p>
    </div>
    <div class="divider"></div>
    <h3>视频模型 · Seedance</h3>
    <div class="field">
      <label class="label" for="video-preset">视频模型</label
      ><select
        id="video-preset"
        v-model="preset"
        :disabled="locked"
        @change="select"
      >
        <option
          v-for="(value, id) in state.status?.video_models"
          :key="id"
          :value="id"
        >
          {{ value.label }}{{ String(id).includes("mini") ? " · 省成本" : "" }}
        </option>
        <option value="custom">其他 / 自定义模型</option>
      </select>
      <p class="hint">
        {{
          profile
            ? `${profile.label}：逐镜头制作使用 720p，并请求生成原生声音。两个模型共用方舟地址和密钥。`
            : "填写服务商给出的模型 ID；自定义模型需兼容当前视频生成接口。"
        }}
      </p>
    </div>
    <div class="field">
      <label class="label" for="video-base">方舟服务地址</label
      ><input
        id="video-base"
        v-model="form.seedance_base_url"
        type="url"
        required
        :disabled="locked"
      />
    </div>
    <div class="grid two">
      <div class="field">
        <label class="label" for="video-model">模型 / 接入点 ID</label
        ><input
          id="video-model"
          v-model="form.seedance_model"
          :readonly="preset !== 'custom'"
          required
          :disabled="locked"
          @change="customChanged"
        />
      </div>
      <div class="field">
        <label class="label" for="video-key">API Key</label
        ><input
          id="video-key"
          v-model="form.seedance_api_key"
          type="password"
          autocomplete="new-password"
          :disabled="locked"
          :placeholder="
            state.status?.settings.seedance_api_key_configured
              ? '已配置，留空保留'
              : '尚未配置'
          "
        />
      </div>
    </div>
    <div class="field">
      <label class="label" for="estimate">每秒视频费用预估（元）</label
      ><input
        id="estimate"
        v-model.number="form.estimate_per_second"
        type="number"
        min="0"
        max="1000"
        step="0.001"
        required
        :disabled="locked"
      />
      <p class="hint">
        请按所选模型的实际报价填写。设为 0 时不能提交 AI
        视频任务。两个模型分别记住费用预估；参考值不是实时报价，不能代替账单。
      </p>
    </div>
    <div class="dialog-actions">
      <button
        type="button"
        class="button ghost"
        :disabled="state.requestPending"
        @click="closeDialog"
      >
        取消</button
      ><button class="button" :disabled="locked">保存设置</button>
    </div>
  </form>
</template>
