<script setup lang="ts">
import { useStudio } from "../composables/useStudio";
import BriefPanel from "../components/BriefPanel.vue";
import StylePanel from "../components/StylePanel.vue";
import PageHeader from "../components/PageHeader.vue";
import Badge from "../components/Badge.vue";
const {
  project,
  state,
  locked,
  activeScript,
  openDialog,
  showProject,
  act,
  api,
} = useStudio();
async function select(id: string) {
  if (project.value.shots.length)
    return openDialog({ kind: "switch-script", id });
  if (await act((pid) => api.selectScript(pid, id)))
    state.selectedShots = new Set(project.value.shots.map((s) => s.id));
}
</script>
<template>
  <PageHeader
    title="挑一个值得继续的故事"
    subtitle="先选制作形式、核对原文并确定剧本，再把台词、动作与反应拆成分镜。"
    ><button
      class="button ghost small"
      :disabled="locked"
      @click="showProject(true)"
    >
      项目设置
    </button></PageHeader
  ><BriefPanel /><StylePanel />
  <div class="panel">
    <div class="panel-title">
      <h2>{{ project.title }}</h2>
      <Badge :tone="project.script_approved ? 'green' : ''">{{
        project.script_approved ? "剧本已确认" : "等待选定"
      }}</Badge>
    </div>
    <p class="muted">{{ project.premise }}</p>
    <div class="actions" style="margin-top: 22px">
      <button
        class="button"
        :disabled="
          locked ||
          !project.style ||
          !state.status?.settings.llm_api_key_configured ||
          !state.status.settings.llm_model ||
          (project.workflow_status.enabled &&
            !project.workflow_status.content_ok)
        "
        @click="act(api.plan)"
      >
        {{
          project.workflow_status.enabled
            ? "按已审剧本生成分镜草案"
            : "生成 AI 剧本方案"
        }}</button
      ><button
        class="button ghost"
        :disabled="locked"
        @click="openDialog({ kind: 'script' })"
      >
        导入 / 手写剧本
      </button>
    </div>
    <p class="hint">
      {{
        state.status?.settings.llm_api_key_configured
          ? "AI 方案将调用已配置的文本服务，可能产生费用。"
          : "尚未配置文本模型，请连接模型或导入自己的剧本。"
      }}
    </p>
  </div>
  <div v-if="project.scripts.length" class="grid three">
    <article
      v-for="(option, index) in project.scripts"
      :key="option.id"
      class="script-card"
      :class="{ selected: option.id === project.active_script }"
    >
      <div class="card-head">
        <span class="index"
          >CONCEPT {{ String(index + 1).padStart(2, "0") }}</span
        ><Badge>{{
          option.source === "ai"
            ? "AI 方案"
            : option.source === "demo"
              ? "示例方案"
              : "手动剧本"
        }}</Badge>
      </div>
      <h2>{{ option.script.title }}</h2>
      <p class="hook">{{ option.script.hook }}</p>
      <p>{{ option.script.synopsis }}</p>
      <div class="meta-row">
        <span>{{ option.script.characters.length }} 名角色</span
        ><span>{{ option.script.shots.length }} 个镜头</span
        ><span
          >{{
            option.script.shots.reduce((sum, s) => sum + s.duration, 0)
          }}
          秒</span
        >
      </div>
      <div class="actions">
        <button
          class="button secondary small"
          :disabled="locked || option.id === project.active_script"
          @click="select(option.id)"
        >
          {{
            option.id === project.active_script ? "✓ 已选用" : "选用此方案"
          }}</button
        ><button
          class="text-button"
          :disabled="locked"
          @click="openDialog({ kind: 'script', id: option.id })"
        >
          编辑副本
        </button>
      </div>
    </article>
  </div>
  <div v-else class="empty">
    剧本候选会出现在这里。先生成方案，或导入自己的剧本。
  </div>
  <div v-if="activeScript" class="bottom-actions">
    <span class="hint"
      >选定：{{ activeScript.title }} · 可在下一步编辑角色和分镜</span
    ><button
      class="button"
      :disabled="locked"
      @click="act((pid) => api.approve(pid, 'script'), 1)"
    >
      {{
        project.script_approved ? "进入角色设定" : "确认剧本，进入角色设定"
      }}
      →
    </button>
  </div>
</template>
