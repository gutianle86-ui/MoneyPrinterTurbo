<script setup lang="ts">
import { useStudio } from "../composables/useStudio";
const { navigate } = useStudio();
</script>
<template>
  <div class="empty">
    <p>请先选择一个剧本方案。</p>
    <button class="button" @click="navigate(0)">返回故事与剧本</button>
  </div>
</template>
