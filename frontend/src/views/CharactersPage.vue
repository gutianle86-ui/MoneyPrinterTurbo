<script setup lang="ts">
import { reactive } from "vue";
import { useStudio } from "../composables/useStudio";
import PageHeader from "../components/PageHeader.vue";
import NeedScript from "../components/NeedScript.vue";
import UploadButton from "../components/UploadButton.vue";
import Badge from "../components/Badge.vue";
const { project, locked, asset, act, api, notify } = useStudio();
const characters = reactive(
  structuredClone(JSON.parse(JSON.stringify(project.value.characters))),
) as typeof project.value.characters;
async function save(approve: boolean) {
  const ok = await act(
    async (pid) => {
      if (
        JSON.stringify(characters) !== JSON.stringify(project.value.characters)
      )
        await api.characters(pid, characters);
      return approve ? api.approve(pid, "characters") : api.project(pid);
    },
    approve ? 2 : undefined,
  );
  if (ok && !approve) notify("角色设定已保存");
}
async function upload(index: number, file: File) {
  if (await act((pid) => api.uploadCharacter(pid, index, file))) {
    characters[index].reference_file =
      project.value.characters[index].reference_file;
    notify("角色参考图已归档；配置方舟素材 URI 后才会用于生成");
  }
}
</script>
<template>
  <NeedScript v-if="!project.active_script" /><template v-else
    ><PageHeader
      title="让角色保持同一个人"
      subtitle="角色描述和已配置的参考素材会随相关镜头一起提交，生成后仍需检查面孔、服装和动作。"
    />
    <div class="grid two">
      <div
        v-for="(character, index) in characters"
        :key="character.name"
        class="panel"
      >
        <div class="character-header">
          <img
            v-if="character.reference_file"
            class="character-reference"
            :src="asset(character.reference_file)"
            :alt="`${character.name}参考图`"
          />
          <div v-else class="portrait-mark">
            {{ character.name.slice(0, 1) }}
          </div>
          <div>
            <h2>{{ character.name }}</h2>
            <p class="hint">
              CHARACTER {{ String(index + 1).padStart(2, "0") }}
            </p>
          </div>
        </div>
        <div class="actions" style="margin-bottom: 18px">
          <UploadButton
            accept=".png,.jpg,.jpeg,.webp"
            :label="
              character.reference_file ? '替换本地参考图' : '上传本地参考图'
            "
            :upload="(file) => upload(index, file)"
          /><Badge v-if="character.reference_file" tone="green">已归档</Badge>
        </div>
        <label class="label" :for="`reference-${index}`"
          >方舟参考素材 URI（AI 视频必填）</label
        ><input
          :id="`reference-${index}`"
          v-model="character.reference_uri"
          :disabled="locked"
          placeholder="asset://asset-... 或 https://..."
        />
        <p class="hint">
          本地图片用于预览和归档，生成前还须填写公网 HTTPS 地址或方舟素材 URI。
        </p>
        <label class="label" :for="`appearance-${index}`"
          >固定外观 · 服装 · 特征</label
        ><textarea
          :id="`appearance-${index}`"
          v-model="character.appearance"
          rows="5"
          maxlength="1000"
          :disabled="locked"
        ></textarea
        ><label class="label" :for="`voice-description-${index}`"
          >角色声音设定（用于 AI 视频提示词）</label
        ><textarea
          :id="`voice-description-${index}`"
          v-model="character.voice_description"
          rows="2"
          maxlength="300"
          :disabled="locked"
        ></textarea>
        <p class="hint">
          描述年龄感、音色、语速和口音。提示词不能保证跨镜头音色一致，需试听样片。
        </p>
        <label class="label" :for="`voice-${index}`"
          >系统试听音色（仅用于预演）</label
        ><input
          :id="`voice-${index}`"
          v-model="character.voice"
          :disabled="locked"
        />
        <p class="hint">这里只控制本机系统朗读，不控制 Seedance 原声。</p>
      </div>
    </div>
    <div class="info">
      画风：{{ project.style
      }}<br />修改角色设定或参考素材后，已有候选会过期，旧版本仍然保留。
    </div>
    <div class="bottom-actions">
      <button class="button secondary" :disabled="locked" @click="save(false)">
        保存角色修改</button
      ><button
        class="button"
        :disabled="locked || !project.script_approved"
        @click="save(true)"
      >
        保存并确认角色 →
      </button>
    </div></template
  >
</template>
