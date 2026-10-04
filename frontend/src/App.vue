<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { useStudio } from "./composables/useStudio";
import { steps, textModels } from "./domain";
import JobPanel from "./components/JobPanel.vue";
import DialogHost from "./components/DialogHost.vue";
import StoryPage from "./views/StoryPage.vue";
import CharactersPage from "./views/CharactersPage.vue";
import ShotsPage from "./views/ShotsPage.vue";
import ProductionPage from "./views/ProductionPage.vue";
import ExportPage from "./views/ExportPage.vue";
const {
  state,
  locked,
  done,
  dialog,
  init,
  stop,
  navigate,
  showProject,
  showSettings,
  changeProject,
  switchModel,
} = useStudio();
const pages = [
  StoryPage,
  CharactersPage,
  ShotsPage,
  ProductionPage,
  ExportPage,
];
onMounted(init);
onBeforeUnmount(stop);
</script>
<template>
  <aside class="sidebar">
    <a class="brand" href="/" aria-label="幕间首页"
      ><span class="brand-icon">幕</span
      ><span>幕间<small>DRAMA WORKSPACE</small></span></a
    >
    <div class="sidebar-label">制作流程</div>
    <nav aria-label="制作阶段">
      <button
        v-for="(step, index) in steps"
        :key="step"
        class="nav-item"
        :class="{ active: state.stage === index }"
        :disabled="!state.project"
        @click="navigate(index)"
      >
        <span class="nav-num">{{ String(index + 1).padStart(2, "0") }}</span
        >{{ step }}<span v-if="done[index]" class="done">✓</span>
      </button>
    </nav>
    <div class="sidebar-bottom">
      <div class="local-dot">本地工作台 <span>V0.2</span></div>
      <button
        class="text-button"
        :disabled="locked || !state.status"
        @click="showSettings"
      >
        ⚙ 服务设置
      </button>
      <p>作品与候选保存在这台电脑。<br />每一步，都可以重新选择。</p>
    </div>
  </aside>
  <div class="workspace">
    <header class="topbar">
      <div class="breadcrumb">
        工作空间 <span>/</span
        ><select
          aria-label="切换项目"
          :value="state.project?.id || ''"
          :disabled="state.requestPending"
          @change="changeProject(($event.target as HTMLSelectElement).value)"
        >
          <option v-if="!state.projects.length" value="">还没有项目</option>
          <option v-for="p in state.projects" :key="p.id" :value="p.id">
            {{ p.title }}
          </option>
        </select>
      </div>
      <div class="actions">
        <template v-if="state.status"
          ><select
            aria-label="切换文本模型"
            :value="state.status.settings.llm_model"
            :disabled="locked"
            @change="
              switchModel('text', ($event.target as HTMLSelectElement).value)
            "
          >
            <option v-for="(label, id) in textModels" :key="id" :value="id">
              {{ label }}
            </option>
            <option
              v-if="!textModels[state.status.settings.llm_model]"
              :value="state.status.settings.llm_model"
            >
              {{ state.status.settings.llm_model || "未配置文本模型" }}
            </option></select
          ><select
            aria-label="切换视频模型"
            :value="state.status.settings.seedance_model"
            :disabled="locked"
            @change="
              switchModel('video', ($event.target as HTMLSelectElement).value)
            "
          >
            <option
              v-for="(profile, id) in state.status.video_models"
              :key="id"
              :value="id"
            >
              {{ profile.label
              }}{{ String(id).includes("mini") ? " · 省成本" : "" }}
            </option>
            <option
              v-if="
                !state.status.video_models[state.status.settings.seedance_model]
              "
              :value="state.status.settings.seedance_model"
            >
              {{ state.status.settings.seedance_model }}
            </option>
          </select></template
        ><button
          class="button secondary small mobile-settings"
          :disabled="locked || !state.status"
          @click="showSettings"
        >
          服务设置</button
        ><button
          class="button secondary small"
          :disabled="locked || !state.status"
          @click="showProject(false)"
        >
          ＋ 新建项目
        </button>
      </div>
    </header>
    <main>
      <div v-if="state.loading" class="empty" role="status">
        正在连接工作台…
      </div>
      <div v-else-if="state.loadError" class="empty">
        <h2>暂时无法连接工作台</h2>
        <p>{{ state.loadError }}</p>
        <button class="button" @click="init">重试</button>
      </div>
      <template v-else-if="state.project"
        ><JobPanel /><component
          :is="pages[state.stage]"
          :key="`${state.project.id}-${state.stage}`"
      /></template>
      <div v-else class="welcome">
        <div class="eyebrow">YOUR FIRST EPISODE</div>
        <h1>从一个故事，到第一集成片。</h1>
        <p class="muted" style="margin-top: 18px">
          先把故事讲顺，再为值得制作的画面花钱。
        </p>
        <div class="steps-mini">
          <span
            v-for="step in [
              '内容策划',
              '固定角色',
              '免费预演',
              '单镜样片',
              '剪辑导出',
            ]"
            :key="step"
            >{{ step }}</span
          >
        </div>
        <div class="panel">
          <div class="panel-title"><h2>从你的小说素材开始</h2></div>
          <p class="muted">
            创建项目，粘贴原文片段或准确梗概，先确定内容策划，再制作分镜和视频。已有剧本也可以直接导入。
          </p>
          <div class="actions" style="margin-top: 24px">
            <button class="button" @click="showProject(false)">
              创建我的故事 →
            </button>
          </div>
          <p class="hint">
            AI
            策划需要在服务设置中配置文本模型。免费文字预演用于检查剧情和节奏，真实画面可由
            AI 服务生成，也可导入已有的视频或图片。
          </p>
        </div>
      </div>
    </main>
    <footer>幕间工作台 <span>故事 · 选择 · 制作</span></footer>
  </div>
  <div
    v-if="state.notice"
    id="notice"
    :class="{ error: state.notice.error }"
    style="display: block"
    role="status"
    aria-live="polite"
  >
    {{ state.notice.message }}
  </div>
  <DialogHost v-if="dialog" />
</template>
