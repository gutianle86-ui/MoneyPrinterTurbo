<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useStudio } from "../composables/useStudio";
import { money, picked, validCandidates } from "../domain";
import PageHeader from "../components/PageHeader.vue";
import NeedScript from "../components/NeedScript.vue";
import PreflightPanel from "../components/PreflightPanel.vue";
import ShotCard from "../components/ShotCard.vue";
const {
  project,
  state,
  locked,
  canMake,
  selectedCount,
  openDialog,
  act,
  api,
  notify,
  navigate,
} = useStudio();
const paid = ref(false);
const checked = computed(() =>
  project.value.shots.filter((s) => state.selectedShots.has(s.id)),
);
const estimate = computed(
  () =>
    checked.value.reduce((sum, s) => sum + s.duration, 0) *
    state.variants *
    (state.status?.settings.estimate_per_second || 0),
);
const shots = computed(() =>
  project.value.shots.filter(
    (s) =>
      state.shotFilter === "all" ||
      (state.shotFilter === "missing" && !picked(s)) ||
      (state.shotFilter === "review" &&
        validCandidates(s).length &&
        !picked(s)),
  ),
);
const blocked = computed(
  () =>
    locked.value ||
    !canMake.value ||
    !checked.value.length ||
    (state.generateMode === "seedance" &&
      project.value.workflow_status.enabled &&
      (project.value.workflow_status.blockers.length > 0 ||
        (!project.value.workflow_status.pilot_ok &&
          (checked.value.length !== 1 || state.variants !== 1)))),
);
watch(
  [
    () => state.generateMode,
    () => state.variants,
    () => [...state.selectedShots].join(","),
    () => state.status?.settings.seedance_model,
    () => state.status?.settings.estimate_per_second,
    () => project.value.workflow_status.story_revision,
  ],
  () => {
    paid.value = false;
  },
);
async function generate() {
  const options = {
    shot_ids: checked.value.map((s) => s.id),
    mode: state.generateMode,
    variants: state.variants,
    confirm_paid: paid.value,
  };
  if (options.mode === "preview") {
    await act((pid) => api.generate(pid, options));
    return;
  }
  if (!paid.value) return notify("请先勾选确认调用付费视频服务", true);
  const settings = state.status!.settings;
  openDialog({
    kind: "generate",
    options,
    revision: project.value.workflow_status.story_revision,
    model: settings.seedance_model,
    rate: settings.estimate_per_second,
  });
}
</script>
<template>
  <NeedScript v-if="!project.active_script" /><template v-else
    ><PageHeader
      title="制作、比较，留下最好的镜头"
      subtitle="每个镜头可以生成多个候选。导入自己的图片或视频，也能进入同一条制作流程。"
      ><button
        class="button secondary"
        :disabled="locked"
        @click="act(api.selectFirst)"
      >
        未选镜头采用首个有效候选
      </button></PageHeader
    >
    <div class="stats">
      <div class="stat">
        <span>已选用镜头</span
        ><b
          >{{ selectedCount }}<small>/ {{ project.shots.length }}</small></b
        >
      </div>
      <div class="stat">
        <span>累计候选</span
        ><b
          >{{ project.shots.reduce((sum, s) => sum + s.candidates.length, 0)
          }}<small>个</small></b
        >
      </div>
      <div class="stat">
        <span>视频生成预估消耗</span><b>{{ money(project.reserved_cost) }}</b>
      </div>
      <div class="stat">
        <span>项目预算</span><b>{{ money(project.budget) }}</b>
      </div>
    </div>
    <div v-if="!canMake" class="info amber">
      先完成剧本、角色和分镜确认，再开始生成。导入素材后同样需要审核才能导出。
    </div>
    <PreflightPanel />
    <div class="panel">
      <div class="toolbar">
        <div class="field">
          <label class="label" for="make-mode">制作方式</label
          ><select
            id="make-mode"
            v-model="state.generateMode"
            :disabled="locked"
          >
            <option value="preview">本地文字预演 · 免费</option>
            <option value="seedance">Seedance · AI 视频</option>
          </select>
        </div>
        <div class="field">
          <label class="label" for="variants">每镜头候选数</label
          ><select
            id="variants"
            v-model.number="state.variants"
            :disabled="locked"
          >
            <option v-for="n in [1, 2, 3]" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="field">
          <label class="label" for="shot-filter">显示</label
          ><select id="shot-filter" v-model="state.shotFilter">
            <option value="all">全部镜头</option>
            <option value="missing">尚未选用</option>
            <option value="review">有候选待筛选</option>
          </select>
        </div>
        <button class="button push" :disabled="blocked" @click="generate">
          制作选中的 {{ checked.length }} 个镜头
        </button>
      </div>
      <div class="actions">
        <button
          class="text-button"
          :disabled="locked"
          @click="state.selectedShots = new Set(project.shots.map((s) => s.id))"
        >
          全选</button
        ><span class="muted">/</span
        ><button
          class="text-button"
          :disabled="locked"
          @click="
            state.selectedShots = new Set(
              project.shots.filter((s) => !picked(s)).map((s) => s.id),
            )
          "
        >
          仅选未完成</button
        ><span class="muted">/</span
        ><button
          class="text-button"
          :disabled="locked"
          @click="state.selectedShots.clear()"
        >
          清空选择
        </button>
      </div>
      <template v-if="state.generateMode === 'seedance'"
        ><div class="budget-line">
          预计 {{ checked.length * state.variants }} 次生成 · 约
          {{ money(estimate) }}
          <label class="check-label"
            ><input
              v-model="paid"
              type="checkbox"
              :disabled="locked"
            />确认调用付费视频服务</label
          >
        </div>
        <p class="hint">
          预算按你填写的每秒费用预估；不是实际账单，也不包含文本模型费用。提交结果未知或已有任务编号时保留预估；任务创建前被明确拒绝则自动释放。{{
            !state.status?.settings.seedance_api_key_configured
              ? "请先配置视频服务密钥。"
              : ""
          }}
        </p></template
      >
      <p v-else class="hint">
        本地预演制作文字分镜卡，不会生成角色画面，也不会调用付费服务。
      </p>
    </div>
    <div class="grid three shot-grid">
      <ShotCard
        v-for="shot in shots"
        :key="shot.id"
        :shot="shot"
        :index="project.shots.indexOf(shot)"
      />
    </div>
    <div v-if="!shots.length" class="empty">当前筛选下没有镜头。</div>
    <div class="bottom-actions">
      <span class="hint"
        >已选用 {{ selectedCount }} / {{ project.shots.length }} 个镜头</span
      ><button class="button" @click="navigate(4)">前往合成与导出 →</button>
    </div></template
  >
</template>
