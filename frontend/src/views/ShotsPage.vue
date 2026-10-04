<script setup lang="ts">
import { useStudio } from "../composables/useStudio";
import PageHeader from "../components/PageHeader.vue";
import NeedScript from "../components/NeedScript.vue";
import PreflightPanel from "../components/PreflightPanel.vue";
import AnimaticPanel from "../components/AnimaticPanel.vue";
import Badge from "../components/Badge.vue";
const { project, state, locked, openDialog, act, api, selectedCount } =
  useStudio();
async function approve() {
  if (
    await act(
      (pid) => api.approve(pid, "shots"),
      project.value.workflow_status.enabled ? 2 : 3,
    )
  ) {
    if (!state.selectedShots.size && !selectedCount.value)
      state.selectedShots = new Set(project.value.shots.map((s) => s.id));
  }
}
function toggle(id: string, checked: boolean) {
  if (checked) state.batchShots.add(id);
  else state.batchShots.delete(id);
}
</script>
<template>
  <NeedScript v-if="!project.active_script" /><template v-else
    ><PageHeader
      title="逐镜头，确认故事怎么发生"
      subtitle="对白、画面和时长都可以修改。确认后再制作，避免为不需要的镜头花钱。"
      ><button
        class="button"
        :disabled="locked || !project.characters_approved"
        @click="approve"
      >
        {{
          project.workflow_status.enabled
            ? "确认全部分镜，开始预演"
            : "确认全部分镜 →"
        }}
      </button></PageHeader
    >
    <div class="stats">
      <div class="stat">
        <span>计划时长</span
        ><b
          >{{ project.shots.reduce((sum, s) => sum + s.duration, 0)
          }}<small>秒</small></b
        >
      </div>
      <div class="stat">
        <span>镜头数量</span><b>{{ project.shots.length }}<small>个</small></b>
      </div>
      <div class="stat">
        <span>已审核</span
        ><b
          >{{ project.shots.filter((s) => s.approved).length
          }}<small>/ {{ project.shots.length }}</small></b
        >
      </div>
      <div class="stat">
        <span>场景</span
        ><b
          >{{ new Set(project.shots.map((s) => s.scene)).size
          }}<small>处</small></b
        >
      </div>
    </div>
    <div class="panel">
      <div class="actions">
        <button
          class="button secondary small"
          :disabled="locked || !state.batchShots.size"
          @click="openDialog({ kind: 'batch' })"
        >
          批量修改时长（{{ state.batchShots.size }}）</button
        ><button
          class="text-button"
          :disabled="locked"
          @click="state.batchShots = new Set(project.shots.map((s) => s.id))"
        >
          全选分镜</button
        ><button
          class="text-button"
          :disabled="locked"
          @click="state.batchShots.clear()"
        >
          清空选择
        </button>
      </div>
      <p class="hint">
        只修改勾选镜头的计划时长；变化的镜头需重审，旧候选保留并过期。
      </p>
    </div>
    <div class="panel table-wrap">
      <table class="shot-table">
        <thead>
          <tr>
            <th>选择</th>
            <th>镜头</th>
            <th>画面与动作</th>
            <th>对白 / 旁白</th>
            <th>时长</th>
            <th>审核</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(shot, index) in project.shots" :key="shot.id">
            <td>
              <input
                type="checkbox"
                :aria-label="`批量选择镜头 ${index + 1}`"
                :checked="state.batchShots.has(shot.id)"
                :disabled="locked"
                @change="
                  toggle(shot.id, ($event.target as HTMLInputElement).checked)
                "
              />
            </td>
            <td>
              <span class="index">{{ String(index + 1).padStart(2, "0") }}</span
              ><br /><strong>{{ shot.title }}</strong
              ><span class="scene">{{ shot.scene }}</span>
            </td>
            <td class="visual">
              {{ shot.visual
              }}<span class="scene"
                ><template v-if="shot.beat_index"
                  >剧本第 {{ shot.beat_index }} 段<br /></template
                >作用：{{ shot.purpose || "未填写" }}<br />起：{{
                  shot.start_state || "未填写"
                }}<br />止：{{ shot.end_state || "未填写" }}</span
              >
            </td>
            <td class="dialogue">
              <span class="scene">{{ shot.speaker }}</span
              >{{ shot.narration || "无对白" }}
            </td>
            <td>{{ shot.duration }}s</td>
            <td>
              <Badge :tone="shot.approved ? 'green' : 'amber'">{{
                shot.approved ? "已确认" : "待审核"
              }}</Badge>
            </td>
            <td>
              <button
                class="button ghost small"
                :disabled="locked"
                @click="openDialog({ kind: 'shot', id: shot.id })"
              >
                编辑
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="hint">修改分镜会使该镜头的旧候选过期。</p>
    <PreflightPanel /><AnimaticPanel
  /></template>
</template>
